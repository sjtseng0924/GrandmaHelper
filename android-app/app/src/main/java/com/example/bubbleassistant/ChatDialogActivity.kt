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
import android.content.Context
import android.widget.Button

class ChatDialogActivity : Activity() {

    private lateinit var editText: EditText
    private lateinit var sendButton: Button
    private lateinit var cancelButton: Button
    private lateinit var dialogBox: View
    private lateinit var rootView: View

    // 三顆快捷按鈕
    private lateinit var shortcut1Button: Button
    private lateinit var shortcut2Button: Button
    private lateinit var shortcut3Button: Button

    // Overlay
    private var wm: WindowManager? = null
    private var stepView: View? = null
    private var stepLp: WindowManager.LayoutParams? = null
    private var steps: MutableList<String> = mutableListOf()
    private var initialUserMsg: String = ""
    private var isBusy: Boolean = false

    // HTTP client
    private val httpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }

    // === TTS Manager ===
    private lateinit var ttsManager: TextToSpeechManager

    // ==== 拖曳狀態 (新增) ====
    private var dragStartY: Int = 0
    private var dragTouchStartY: Float = 0f
    private var isDragging: Boolean = false
    private val touchSlop: Int by lazy { ViewConfiguration.get(this).scaledTouchSlop }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 對話框樣式
        window.setBackgroundDrawable(ColorDrawable(android.graphics.Color.TRANSPARENT))
        window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        window.setGravity(Gravity.CENTER)
        setContentView(R.layout.dialog_chat)

        // 先套用三個快捷文字
        applyShortcutTexts()

        // 綁定
        editText = findViewById(R.id.input_message)
        sendButton = findViewById(R.id.send_button)
        cancelButton = findViewById(R.id.cancel_button)
        rootView = findViewById(R.id.dialog_root)
        dialogBox = findViewById(R.id.dialog_box)

        // 三顆快捷鍵 → 等同送出流程
        shortcut1Button = findViewById(R.id.shortcut1)
        shortcut2Button = findViewById(R.id.shortcut2)
        shortcut3Button = findViewById(R.id.shortcut3)
        shortcut1Button.setOnClickListener { handleShortcutClick(shortcut1Button.text?.toString().orEmpty()) }
        shortcut2Button.setOnClickListener { handleShortcutClick(shortcut2Button.text?.toString().orEmpty()) }
        shortcut3Button.setOnClickListener { handleShortcutClick(shortcut3Button.text?.toString().orEmpty()) }

        wm = applicationContext.getSystemService(WINDOW_SERVICE) as WindowManager

        // 初始化 TTS
        ttsManager = TextToSpeechManager.getInstance(this)

        // 送出
        sendButton.setOnClickListener {
            val message = editText.text.toString().trim()
            if (message.isEmpty() || isBusy) return@setOnClickListener
            isBusy = true
            initialUserMsg = message
            sendButton.isEnabled = false
            OverlayAgent.taskActive = true

            // 收鍵盤並關閉對話框
            try {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
                imm.hideSoftInputFromWindow(editText.windowToken, 0)
            } catch (_: Exception) {}
            finish()

            // 主流程
            OverlayAgent.scope.launch {
                // 1) 先監控（overlay 隱藏中）
                val screenInfo = runWithOverlayHiddenDuringMonitoring { getRealTimeScreenInfo() }

                // 2) 監控完成後，立刻顯示「請稍候…」
                withContext(Dispatchers.Main) { showPleaseWait() }

                // 3) 再呼叫 API
                val serverMessage = withContext(Dispatchers.IO) {
                    OverlayAgent.callAssistantApi(
                        userMsg = initialUserMsg,
                        goal = initialUserMsg,
                        summaryText = screenInfo,
                        timestampMs = System.currentTimeMillis()
                    )
                }.trim()

                // 4) 收到回覆後更新 overlay
                withContext(Dispatchers.Main) {
                    when {
                        serverMessage.contains("沒有明確目的") -> {
                            val msg = "您的輸入沒有明確目的，請告訴我您想要做到的事情喔!"
                            steps = mutableListOf(msg)
                            updateStepText()
                            showAutoDismiss(msg) // 自動關閉，且不顯示勾選
                        }
                        serverMessage.contains("恭喜成功") -> {
                            steps = mutableListOf("🎉 恭喜成功！")
                            updateStepText()
                            showSuccessThenDismiss()
                        }
                        else -> {
                            steps = mutableListOf(serverMessage.ifBlank { "請依畫面提示操作下一步" })
                            updateStepText()
                            stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = true
                        }
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

    override fun onResume() {
        super.onResume()
        applyShortcutTexts()
    }

    // 讓快捷鍵行為等同按「送出」
    private fun handleShortcutClick(text: String) {
        if (text.isBlank() || ::sendButton.isInitialized.not() || isBusy) return
        editText.setText(text)
        sendButton.performClick()
    }

    // ===== Overlay：顯示請稍候 =====
    private fun showPleaseWait() {
        steps = mutableListOf("請稍候…")
        showStepOverlay()
        stepView?.visibility = View.VISIBLE
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
    }

    // 監控期間只把 overlay 隱藏；結束後不自動改回來，讓呼叫端決定何時顯示
    private suspend fun <T> runWithOverlayHiddenDuringMonitoring(block: suspend () -> T): T {
        return try {
            withContext(Dispatchers.Main) { stepView?.visibility = View.GONE }
            block()
        } finally {
            // 不在這裡自動顯示或改文字
        }
    }

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
            enableOverlayDrag() // ← 新增：啟用拖曳
        }
        updateStepText()
    }

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
            if (currentText.contains("沒有明確目的")) {
                // 若目前就是「沒有明確目的」訊息，直接自動關閉
                showAutoDismiss(currentText)
                isBusy = false
                return@setOnCheckedChangeListener
            }

            OverlayAgent.scope.launch {
                val screenInfo = runWithOverlayHiddenDuringMonitoring { getRealTimeScreenInfo() }
                withContext(Dispatchers.Main) { showPleaseWait() }
                val nextMsg = withContext(Dispatchers.IO) {
                    OverlayAgent.callAssistantApi(
                        userMsg = initialUserMsg,
                        goal = initialUserMsg,
                        summaryText = screenInfo,
                        timestampMs = System.currentTimeMillis()
                    )
                }.trim()

                withContext(Dispatchers.Main) {
                    when {
                        nextMsg.contains("沒有明確目的") -> {
                            val msg = "您的輸入沒有明確目的，請告訴我您想要做到的事情喔!"
                            steps = mutableListOf(msg)
                            updateStepText()
                            showAutoDismiss(msg)
                        }
                        nextMsg.contains("恭喜成功") -> {
                            steps = mutableListOf("恭喜成功！")
                            updateStepText()
                            showSuccessThenDismiss()
                        }
                        else -> {
                            steps = mutableListOf(nextMsg.ifBlank { "請依畫面提示操作下一步" })
                            updateStepText()
                            stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = true
                        }
                    }
                    isBusy = false
                }
            }
        }

        stepView!!.findViewById<ImageButton>(R.id.btn_close).setOnClickListener {
            steps = mutableListOf("已關閉任務，有問題請再次點擊泡泡詢問喔！")
            updateStepText()
            stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
            stepView?.postDelayed({
                dismissOverlay()
                OverlayAgent.taskActive = false
            }, 2000)
        }
    }

    // === 新增：讓 overlay 可拖曳（主要是拖動 Y；X 也支援，但你的寬是 MATCH_PARENT，所以看不太出來） ===
    private fun enableOverlayDrag() {
        val sv = stepView ?: return

        fun hit(view: View?, rawX: Float, rawY: Float): Boolean {
            if (view == null || view.visibility != View.VISIBLE) return false
            val r = Rect()
            view.getGlobalVisibleRect(r)
            return r.contains(rawX.toInt(), rawY.toInt())
        }

        sv.setOnTouchListener { _, event ->
            // 避免和「勾選 / 關閉」衝突：如果按在它們上面就不攔截
            val check = stepView?.findViewById<CheckBox>(R.id.btn_check)
            val close = stepView?.findViewById<ImageButton>(R.id.btn_close)
            if (hit(check, event.rawX, event.rawY) || hit(close, event.rawX, event.rawY)) {
                return@setOnTouchListener false
            }

            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    isDragging = false
                    dragTouchStartY = event.rawY
                    dragStartY = stepLp?.y ?: 0
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dy = (event.rawY - dragTouchStartY).toInt()
                    if (!isDragging && kotlin.math.abs(dy) > touchSlop) {
                        isDragging = true
                    }
                    if (isDragging) {
                        val displayH = resources.displayMetrics.heightPixels
                        val viewH = sv.height.takeIf { it > 0 } ?: 200
                        val maxY = (displayH - viewH).coerceAtLeast(0)
                        val newY = (dragStartY + dy).coerceIn(0, maxY)
                        stepLp?.y = newY
                        try { wm?.updateViewLayout(stepView, stepLp) } catch (_: Exception) {}
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    val wasDragging = isDragging
                    isDragging = false
                    wasDragging
                }
                else -> false
            }
        }
    }

    // === 更新文字並同時播報 ===
    private fun updateStepText() {
        val tv = stepView?.findViewById<TextView>(R.id.tv_step) ?: return
        val text = steps.firstOrNull().orEmpty()
        tv.text = text

        val showCheckbox = !(text.contains("恭喜成功")
                || text.contains("已關閉任務")
                || text.contains("請稍候")
                || text.contains("沒有明確目的"))
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = showCheckbox

        if (text.isNotBlank()) {
            TextToSpeechManager.getInstance(applicationContext).speak(text)
        }
    }

    private fun speakMessage(text: String) {
        val uniqueId = "msg_${System.currentTimeMillis()}"
        ttsManager.speak(text, uniqueId)
    }

    private fun showSuccessThenDismiss() {
        val tv = stepView?.findViewById<TextView>(R.id.tv_step) ?: return
        tv.text = "恭喜成功！"
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
        stepView?.visibility = View.VISIBLE
        stepView?.postDelayed({
            dismissOverlay()
            OverlayAgent.taskActive = false
        }, 1200)
    }

    // === 新增：顯示訊息並自動關閉（用於「沒有明確目的」） ===
    private fun showAutoDismiss(message: String, delayMs: Long = 2000) {
        val tv = stepView?.findViewById<TextView>(R.id.tv_step) ?: return
        tv.text = message
        stepView?.findViewById<CheckBox>(R.id.btn_check)?.isVisible = false
        stepView?.visibility = View.VISIBLE
        stepView?.postDelayed({
            dismissOverlay()
            OverlayAgent.taskActive = false
        }, delayMs)
    }

    private fun dismissOverlay() {
        stepView?.let { v ->
            try { wm?.removeView(v) } catch (_: Exception) {}
        }
        stepView = null
        stepLp = null
        steps.clear()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density + 0.5f).toInt()

    // ===== 擷取螢幕資訊 =====
    private fun getRealTimeScreenInfo(): String {
        try { ScreenMonitor.activateMonitoring() } catch (_: Throwable) {}
        try {
            val forced = ScreenMonitor.forceRefreshScreenInfo()
            if (forced.isNotBlank() && !forced.contains("Waiting for elements")) {
                try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
                return forced
            }
        } catch (_: Throwable) {}

        val url = "http://127.0.0.1:${ScreenInfoServer.DEFAULT_PORT}/screen-info"
        val request = Request.Builder().url(url).build()
        try {
            httpClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val jsonString = response.body?.string().orEmpty()
                    val jsonObject = JSONObject(jsonString)
                    var summaryText = jsonObject.optString("summaryText", "")
                    if (summaryText.contains("Waiting for elements")) {
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
            val direct = try { ScreenMonitor.getLatestScreenInfo() } catch (_: Throwable) { "" }
            try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
            if (direct.isNotBlank()) return direct
        }

        try { ScreenMonitor.deactivateMonitoring() } catch (_: Throwable) {}
        return "無法獲取螢幕資訊"
    }

    private fun applyShortcutTexts() {
        val btn1 = findViewById<Button>(R.id.shortcut1)
        val btn2 = findViewById<Button>(R.id.shortcut2)
        val btn3 = findViewById<Button>(R.id.shortcut3)

        val p = getSharedPreferences("shortcut_prefs", Context.MODE_PRIVATE)
        fun savedOrDefault(key: String, def: String): String {
            val saved = p.getString(key, null)
            return if (saved.isNullOrBlank()) def else saved
        }

        btn1.text = savedOrDefault("shortcut_1", btn1.text?.toString().orEmpty())
        btn2.text = savedOrDefault("shortcut_2", btn2.text?.toString().orEmpty())
        btn3.text = savedOrDefault("shortcut_3", btn3.text?.toString().orEmpty())
    }

    override fun onDestroy() {
        super.onDestroy()
    }
}