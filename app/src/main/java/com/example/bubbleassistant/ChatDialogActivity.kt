package com.example.bubbleassistant

import android.app.Activity
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.ColorDrawable
import android.os.Build
import android.os.Bundle
import android.view.*
import android.widget.*
import androidx.core.view.isVisible
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class ChatDialogActivity : Activity() {

    private lateinit var editText: EditText
    private lateinit var sendButton: Button
    private lateinit var cancelButton: Button
    private lateinit var dialogBox: View
    private lateinit var rootView: View

    // Overlay
    private var wm: WindowManager? = null
    private var stepView: View? = null
    private var stepLp: WindowManager.LayoutParams? = null
    private var steps: MutableList<String> = mutableListOf() // 只放一行
    private var initialUserMsg: String = ""
    private var isBusy: Boolean = false

    // HTTP client for fetching screen info
    private val httpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 對話框樣式
        window.setBackgroundDrawable(ColorDrawable(android.graphics.Color.TRANSPARENT))
        window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        window.setGravity(Gravity.CENTER)
        setContentView(R.layout.dialog_chat)

        // 綁定
        editText = findViewById(R.id.input_message)
        sendButton = findViewById(R.id.send_button)
        rootView = findViewById(R.id.dialog_root)
        dialogBox = findViewById(R.id.dialog_box)
        val cancelButton: Button = findViewById(R.id.cancel_button)

        wm = applicationContext.getSystemService(WINDOW_SERVICE) as WindowManager

        // 送出
        sendButton.setOnClickListener {
            val message = editText.text.toString().trim()
            if (message.isEmpty() || isBusy) return@setOnClickListener
            isBusy = true
            initialUserMsg = message
            sendButton.isEnabled = false
            OverlayAgent.taskActive = true
            // 收鍵盤並關閉對話框（不讓它擋畫面）
            try {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                imm.hideSoftInputFromWindow(editText.windowToken, 0)
            } catch (_: Exception) {}
            finish()

            // 主流程
            OverlayAgent.scope.launch {
                // 先顯示「請稍候…」（勾選框隱藏）
                withContext(Dispatchers.Main) { showPleaseWait() }

                // 只有「監控擷取瞬間」把 overlay 完全隱藏，其餘時間顯示「請稍候…」
                val screenInfo = runWithOverlayHiddenDuringMonitoring {
                    getRealTimeScreenInfo()
                }

                // 呼叫後端取得下一步
                val serverMessage = withContext(Dispatchers.IO) {
                    OverlayAgent.callAssistantApi(
                        userMsg = initialUserMsg,
                        goal = initialUserMsg,
                        summaryText = screenInfo,
                        timestampMs = System.currentTimeMillis()
                    )
                }.trim()

                withContext(Dispatchers.Main) {
                    if (serverMessage.contains("恭喜成功")) {
                        steps = mutableListOf("🎉 恭喜成功！")
                        updateStepText()
                        showSuccessThenDismiss()
                    } else {
                        steps = mutableListOf(serverMessage.ifBlank { "請依畫面提示操作下一步" })
                        updateStepText()
                        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = true
                    }
                    isBusy = false
                }
            }
        }

        cancelButton.setOnClickListener {
            try {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                imm.hideSoftInputFromWindow(editText.windowToken, 0)
            } catch (_: Exception) {}
            finish()
        }

        // 點外面關閉
        rootView.setOnTouchListener { _, e ->
            if (e.action == MotionEvent.ACTION_DOWN) {
                val rect = Rect()
                dialogBox.getGlobalVisibleRect(rect)
                if (!rect.contains(e.rawX.toInt(), e.rawY.toInt())) {
                    finish(); return@setOnTouchListener true
                }
            }
            false
        }
    }

    // ===== Overlay：顯示請稍候（勾選框隱藏）=====
    private fun showPleaseWait() {
        steps = mutableListOf("請稍候…")
        showStepOverlay()
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
    }

    /** 在「監控擷取」期間把 overlay 完全隱藏；其餘時間維持請稍候畫面 */
    private suspend fun <T> runWithOverlayHiddenDuringMonitoring(block: suspend () -> T): T {
        return try {
            withContext(Dispatchers.Main) { stepView?.visibility = View.GONE }
            block()
        } finally {
            withContext(Dispatchers.Main) {
                // 回到「請稍候…」畫面（勾選框仍隱藏）
                stepView?.visibility = View.VISIBLE
                steps = mutableListOf("請稍候…")
                updateStepText()
                stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
            }
        }
    }

    /** 顯示/更新頂部步驟（只顯示目前一步） */
    private fun showStepOverlay() {
        if (steps.isEmpty()) return
        if (stepView == null) {
            stepView = layoutInflater.inflate(R.layout.step_overlay, null)
            stepLp = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                else
                    WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                        WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM,
                PixelFormat.TRANSLUCENT
            ).apply {
                gravity = Gravity.TOP
                x = 0
                y = dp(12)
            }
            wm?.addView(stepView, stepLp)
            bindStepEvents()
        }
        updateStepText()
    }

    /** 勾選後：再次擷取監控 → call 後端 → 只有含「恭喜成功」才收尾 */
    private fun bindStepEvents() {
        val cb = stepView!!.findViewById<CheckBox>(R.id.btn_check)
        cb.isChecked = false

        cb.setOnCheckedChangeListener { _, isChecked ->
            if (!isChecked || isBusy) return@setOnCheckedChangeListener
            isBusy = true
            cb.isChecked = false

            val currentText = steps.firstOrNull().orEmpty().trim()
            if (currentText.contains("恭喜成功")) {
                showSuccessThenDismiss()
                isBusy = false
                return@setOnCheckedChangeListener
            }

            // 進入請稍候狀態（勾選框隱藏）
            showPleaseWait()

            OverlayAgent.scope.launch {
                // 只有監控擷取期間把 overlay 隱藏
                val screenInfo = runWithOverlayHiddenDuringMonitoring {
                    getRealTimeScreenInfo()
                }

                val nextMsg = withContext(Dispatchers.IO) {
                    OverlayAgent.callAssistantApi(
                        userMsg = initialUserMsg,
                        goal = initialUserMsg,
                        summaryText = screenInfo,
                        timestampMs = System.currentTimeMillis()
                    )
                }.trim()

                withContext(Dispatchers.Main) {
                    if (nextMsg.contains("恭喜成功")) {
                        steps = mutableListOf("🎉 恭喜成功！")
                        updateStepText()
                        showSuccessThenDismiss()
                    } else {
                        steps = mutableListOf(nextMsg.ifBlank { "請依畫面提示操作下一步" })
                        updateStepText()
                        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = true
                    }
                    isBusy = false
                }
            }
        }

        stepView!!.findViewById<ImageButton>(R.id.btn_close).setOnClickListener {
            steps = mutableListOf("已關閉任務，有問題請再次點擊泡泡詢問喔！")
            updateStepText()
            stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
            stepView?.postDelayed({ dismissOverlay()
                OverlayAgent.taskActive = false}, 1200)
        }
    }

    private fun updateStepText() {
        val tv = stepView?.findViewById<TextView>(R.id.tv_step) ?: return
        val text = steps.firstOrNull().orEmpty()
        tv.text = text
        val showCheckbox = !(text.contains("恭喜成功") || text.contains("已關閉任務") || text.contains("請稍候"))
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = showCheckbox
    }

    private fun showSuccessThenDismiss() {
        val tv = stepView?.findViewById<TextView>(R.id.tv_step) ?: return
        tv.text = "🎉 恭喜成功！"
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
        stepView?.visibility = View.VISIBLE
        stepView?.postDelayed({ dismissOverlay()
            OverlayAgent.taskActive = false}, 1200)
    }

    private fun dismissOverlay() {
        stepView?.let { v -> try { wm?.removeView(v) } catch (_: Exception) {} }
        stepView = null
        stepLp = null
        steps.clear()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density + 0.5f).toInt()

    // ===== 擷取螢幕資訊（監控邏輯集中於此；外部已保證擷取時 overlay 會隱藏）=====
    private fun getRealTimeScreenInfo(): String {
        // 確保監控服務啟用（只在擷取過程）
        try { ScreenMonitor.activateMonitoring() } catch (_: Throwable) {}

        // 先嘗試強制刷新（最快）
        try {
            val forced = ScreenMonitor.forceRefreshScreenInfo()
            if (forced.isNotBlank() && !forced.contains("Waiting for elements")) {
                try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
                return forced
            }
        } catch (_: Throwable) {}

        // HTTP 方式
        val url = "http://127.0.0.1:${ScreenInfoServer.DEFAULT_PORT}/screen-info"
        val request = Request.Builder().url(url).build()
        try {
            httpClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val jsonString = response.body?.string().orEmpty()
                    val jsonObject = JSONObject(jsonString)
                    var summaryText = jsonObject.optString("summaryText", "")
                    if (summaryText.contains("Waiting for elements")) {
                        // 再做一次強制刷新，若成功就用強刷結果
                        val forced2 = try { ScreenMonitor.forceRefreshScreenInfo() } catch (_: Throwable) { "" }
                        if (forced2.isNotBlank() && !forced2.contains("Waiting for elements")) {
                            summaryText = forced2
                        }
                    }
                    try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
                    if (summaryText.isNotBlank()) return summaryText
                } else {
                    throw IOException("HTTP ${response.code}")
                }
            }
        } catch (_: Exception) {
            // 直接向監控服務拉一次最新內容作為備援
            val direct = try { ScreenMonitor.getLatestScreenInfo() } catch (_: Throwable) { "" }
            try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
            if (direct.isNotBlank()) return direct
        }

        // 最後兜底
        try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
        return "無法獲取螢幕資訊"
    }
}
