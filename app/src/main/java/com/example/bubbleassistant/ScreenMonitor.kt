package com.example.bubbleassistant

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.util.Log
import android.widget.TextView
import com.example.bubbleassistant.R
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicBoolean

class ScreenMonitor : AccessibilityService() {

    private val TAG = "ScreenMonitor"

    private lateinit var windowManager: WindowManager
    private var overlayView: View? = null
    private var overlayTextView: TextView? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private var eventCount = 0

    // Lightweight HTTP server to expose screen info to LAN/ADB
    private var screenInfoServer: ScreenInfoServer? = null
    private val latestScreenInfoJson = AtomicReference("{\"summaryText\":\"Waiting for elements...\",\"timestampMs\":0}")
    private val onDemandActive = AtomicBoolean(false)
    private val autoTimeoutMs: Long = 2000L
    
    // 靜態引用，供其他類別直接訪問
    companion object {
        private var instance: ScreenMonitor? = null
        
        fun getInstance(): ScreenMonitor? = instance
        
        fun activateMonitoring() {
            instance?.let { monitor ->
                if (!monitor.onDemandActive.getAndSet(true)) {
                    Log.i("ScreenMonitor", "🟢 啟用按需監控")
                    monitor.startServerIfNeeded()
                    monitor.mainHandler.post { monitor.setupOverlay() }
                    // 啟用時立即觸發一次掃描，避免回傳預設 Waiting 內容
                    Thread {
                        try {
                            monitor.tryGetDataFromAllWindows()
                            Thread.sleep(150)
                            monitor.tryGetDataFromAllWindows()
                        } catch (_: Throwable) {}
                    }.start()
                    // 自動超時關閉，避免卡住持續監控
                    monitor.mainHandler.postDelayed({
                        if (monitor.onDemandActive.get()) {
                            Log.i("ScreenMonitor", "⏲️ 按需監控自動超時，執行停用")
                            deactivateMonitoring()
                        }
                    }, monitor.autoTimeoutMs)
                }
            }
        }
        
        fun deactivateMonitoring() {
            instance?.let { monitor ->
                if (monitor.onDemandActive.getAndSet(false)) {
                    Log.i("ScreenMonitor", "⚪ 停用按需監控")
                    monitor.stopServerIfRunning()
                    monitor.mainHandler.post { monitor.removeOverlay() }
                }
            }
        }
        
        fun getLatestScreenInfo(): String {
            return instance?.let { monitor ->
                val json = monitor.latestScreenInfoJson.get()
                try {
                    val jsonObject = JSONObject(json)
                    jsonObject.optString("summaryText", "無法獲取螢幕資訊")
                } catch (e: Exception) {
                    "無法解析螢幕資訊: ${e.message}"
                }
            } ?: "螢幕監控服務未運行"
        }
        
        fun forceRefreshScreenInfo(): String {
            return instance?.let { monitor ->
                Log.i("ScreenMonitor", "🔄 強制刷新螢幕資訊")
                // 強制刷新所有視窗，專注在 LINE 上
                try {
                    Log.i("ScreenMonitor", "🔍 強制掃描所有視窗，尋找 LINE 應用")
                    monitor.tryGetDataFromAllWindows()
                    // 等待一下讓螢幕資訊更新
                    Thread.sleep(200)
                } catch (e: Exception) {
                    Log.w("ScreenMonitor", "強制刷新失敗: ${e.message}")
                }
                getLatestScreenInfo()
            } ?: "螢幕監控服務未運行"
        }
    }

    // 當服務連接時呼叫
    override fun onServiceConnected() {
        super.onServiceConnected()
        Log.d(TAG, "Accessibility Service Connected!")
        
        // 設置靜態引用
        instance = this

        // 可選：設定服務資訊 - 這些設定會覆蓋 XML 中的配置
        val info = serviceInfo
        // 擴展事件類型以捕獲更多區域的資料
        info.eventTypes = AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED or
                AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                AccessibilityEvent.TYPE_VIEW_CLICKED or
                AccessibilityEvent.TYPE_VIEW_FOCUSED or
                AccessibilityEvent.TYPE_VIEW_SCROLLED or
                AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED or
                AccessibilityEvent.TYPE_VIEW_SELECTED or
                AccessibilityEvent.TYPE_ANNOUNCEMENT or
                AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED or
                AccessibilityEvent.TYPE_WINDOWS_CHANGED or
                AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED

        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_SPOKEN
        info.flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
                AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS or
                AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE or
                AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        info.notificationTimeout = 50 // 降低延遲以更快響應
        this.serviceInfo = info

        // 不在啟動時建立 overlay，按需時才建立

        // 僅在按需啟用時啟動 HTTP 伺服器
        startServerIfNeeded()
    }

    // 當輔助功能事件發生時呼叫
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) {
            return
        }

        // 未啟用按需監控時，保持靜默
        if (!onDemandActive.get()) {
            return
        }

        Log.d(TAG, "Event Type: ${AccessibilityEvent.eventTypeToString(event.eventType)}")
        Log.d(TAG, "Event Package Name: ${event.packageName}")
        Log.d(TAG, "Event Class Name: ${event.className}")
        Log.d(TAG, "Event Text: ${event.text}")
        
        // 每 10 次事件顯示一次狀態
        eventCount++
        if (eventCount % 10 == 0) {
            Log.i(TAG, "📊 螢幕監控服務運行中 - 已處理 $eventCount 個事件")
            Log.i(TAG, "📊 當前應用: ${event.packageName}")
            Log.i(TAG, "📊 事件類型: ${AccessibilityEvent.eventTypeToString(event.eventType)}")
        }

        // 忽略我們自己的應用程式事件
        if (event.packageName == "com.example.bubbleassistant") {
            Log.d(TAG, "忽略 GrandmaHelper 自己的事件")
            return
        }

        // 獲取當前視窗的根節點
        val rootNode: AccessibilityNodeInfo? = rootInActiveWindow

        if (rootNode != null) {
            Log.d(TAG, "Root Node Class Name: ${rootNode.className}")
            Log.d(TAG, "Root Node View Id Resource Name: ${rootNode.viewIdResourceName}")
            Log.d(TAG, "Root Node Package Name: ${rootNode.packageName}")
            Log.d(TAG, "Root Node Child Count: ${rootNode.childCount}")
            
            // 忽略我們自己的視窗
            if (rootNode.packageName == "com.example.bubbleassistant") {
                Log.d(TAG, "忽略 GrandmaHelper 自己的視窗")
                return
            }
            
            // 特別針對 LINE 應用進行深度內容掃描
            if (event.packageName == "jp.naver.line.android") {
                Log.d(TAG, "LINE app detected, performing deep content scan...")
                val lineContentSummary = buildLineSpecificSummary(rootNode)
                if (lineContentSummary.isNotEmpty() && !lineContentSummary.contains("No LINE content detected")) {
                    Log.d(TAG, "LINE content found, updating display")
                    updateLatestScreenInfo(lineContentSummary)
                    updateOverlay(lineContentSummary)
                } else {
                    Log.w(TAG, "No LINE content found: $lineContentSummary")
                    // 如果沒找到內容，使用通用掃描結果
                    val summary = buildNodeSummary(rootNode, maxItems = 100)
                    updateLatestScreenInfo("LINE General Scan:\n$summary")
                    updateOverlay("LINE General Scan:\n$summary")
                }
            } else {
                // 非 LINE 應用，使用通用掃描
                val summary = buildNodeSummary(rootNode, maxItems = 100)
                updateLatestScreenInfo(summary)
                updateOverlay(summary)
            }
            
            // 如果摘要為空或項目很少，嘗試獲取所有窗口
            val currentSummary = latestScreenInfoJson.get()
            if (currentSummary.contains("Captured elements: 0") || currentSummary.contains("Captured elements: 1")) {
                tryGetDataFromAllWindows()
            }
        } else {
            Log.w(TAG, "Root node is null. Trying alternative methods...")
            tryGetDataFromAllWindows()
        }
    }

    // 當服務被中斷時呼叫
    override fun onInterrupt() {
        Log.d(TAG, "Accessibility Service Interrupted.")
    }

    // 當服務取消綁定時呼叫
    override fun onUnbind(intent: android.content.Intent?): Boolean {
        Log.d(TAG, "Accessibility Service Unbound.")
        removeOverlay()
        stopServerIfRunning()
        instance = null
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
        stopServerIfRunning()
    }

    // --- Overlay helpers ---
    private fun setupOverlay() {
        try {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                Log.w(TAG, "Overlay not supported on this Android version (< Q). Skipping overlay setup.")
                return
            }
            windowManager = getSystemService(WINDOW_SERVICE) as WindowManager

            val inflater = LayoutInflater.from(this)
            val view = inflater.inflate(R.layout.overlay_view, null)
            val textView = view.findViewById<TextView>(R.id.tvContent)

            val layoutParams = WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                        WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT
            )
            layoutParams.gravity = Gravity.TOP or Gravity.END
            layoutParams.x = 8
            layoutParams.y = 50

            overlayView = view
            overlayTextView = textView
            windowManager.addView(view, layoutParams)
        } catch (t: Throwable) {
            Log.e(TAG, "Failed to setup overlay", t)
        }
    }

    private fun removeOverlay() {
        try {
            overlayView?.let { view ->
                windowManager.removeView(view)
            }
        } catch (_: Throwable) {
        } finally {
            overlayView = null
            overlayTextView = null
        }
    }

    private fun updateOverlay(text: String) {
        if (!onDemandActive.get()) return
        mainHandler.post {
            if (overlayView == null) setupOverlay()
            val summary = when {
                text.contains("LINE app detected") -> "LINE 監控中"
                text.contains("Captured elements: 0") -> "等待中"
                else -> "監控中"
            }
            overlayTextView?.text = summary
        }
    }

    private fun updateLatestScreenInfo(summary: String) {
        val escaped = escapeJsonString(summary)
        val json = "{\"summaryText\":\"$escaped\",\"timestampMs\":${System.currentTimeMillis()}}"
        latestScreenInfoJson.set(json)
        
        Log.i("ScreenMonitor", "💾 更新螢幕資訊快取")
        Log.i("ScreenMonitor", "📱 螢幕資訊長度: ${summary.length} 字元")
        Log.i("ScreenMonitor", "⏰ 更新時間: ${System.currentTimeMillis()}")
        
        // 顯示螢幕資訊的前 100 字元
        if (summary.length > 100) {
            Log.i("ScreenMonitor", "📱 螢幕資訊預覽: ${summary.take(100)}...")
        } else {
            Log.i("ScreenMonitor", "📱 螢幕資訊: $summary")
        }
    }

    private fun escapeJsonString(input: String): String {
        val sb = StringBuilder(input.length + 16)
        input.forEach { ch ->
            when (ch) {
                '\\' -> sb.append("\\\\")
                '"' -> sb.append("\\\"")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    private fun stopServerIfRunning() {
        try {
            screenInfoServer?.stop()
        } catch (_: Throwable) {
        } finally {
            screenInfoServer = null
        }
    }

    private fun startServerIfNeeded() {
        try {
            if (onDemandActive.get() && screenInfoServer == null) {
                screenInfoServer = ScreenInfoServer(jsonProvider = { latestScreenInfoJson.get() }).also { it.start() }
                Log.i(TAG, "ScreenInfoServer started on port ${ScreenInfoServer.DEFAULT_PORT}")
            }
        } catch (t: Throwable) {
            Log.e(TAG, "Failed to start ScreenInfoServer", t)
        }
    }

    // --- Node summary builder ---
    private fun buildNodeSummary(root: AccessibilityNodeInfo, maxItems: Int = 200): String {
        val items = mutableListOf<String>()
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(root)

        while (queue.isNotEmpty() && items.size < maxItems) {
            val node = queue.removeFirst()

            val text = (node.text?.toString()?.takeIf { it.isNotBlank() }
                ?: node.contentDescription?.toString()?.takeIf { it.isNotBlank() }
                ?: if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    node.hintText?.toString()?.takeIf { it.isNotBlank() }
                } else null)
            val viewId = node.viewIdResourceName
            val className = node.className?.toString()

            val rect = Rect()
            node.getBoundsInScreen(rect)
            
            // 更寬鬆的可見性檢查
            val isVisible = rect.width() > 0 && rect.height() > 0

            // 更寬鬆的包含條件，抓取更多元素
            val shouldInclude = text != null || 
                    (viewId != null && viewId.isNotBlank()) ||
                    node.isClickable ||
                    node.isCheckable ||
                    node.isEditable ||
                    node.isScrollable ||
                    node.isSelected ||
                    node.isFocused ||
                    (className != null && isImportantClass(className)) ||
                    (node.childCount > 0 && rect.width() > 20 && rect.height() > 20) || // 降低容器大小要求
                    (className != null && (className.contains("View") || className.contains("Layout"))) // 包含更多 View 類型

            if (shouldInclude && isVisible) {
                val label = buildString {
                    if (text != null) append("\u2022 \"$text\"") else append("\u2022 (no text)")
                    if (!viewId.isNullOrBlank()) append("  [id=$viewId]")
                    if (!className.isNullOrBlank()) append("  <$className>")
                    
                    // 添加交互性標記
                    val interactions = mutableListOf<String>()
                    if (node.isClickable) interactions.add("clickable")
                    if (node.isEditable) interactions.add("editable")
                    if (node.isCheckable) interactions.add("checkable")
                    if (node.isScrollable) interactions.add("scrollable")
                    if (node.isSelected) interactions.add("selected")
                    if (node.isFocused) interactions.add("focused")
                    if (interactions.isNotEmpty()) append("  {${interactions.joinToString(",")}}")
                    
                    append("  @(${rect.left},${rect.top},${rect.width()}x${rect.height()})")
                }
                items.add(label)
            }

            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { child ->
                    queue.add(child)
                }
            }
        }

        val header = "Captured elements: ${items.size} (showing up to $maxItems)"
        return (sequenceOf(header) + items.asSequence()).joinToString(separator = "\n")
    }
    
    private fun isImportantClass(className: String): Boolean {
        return className.contains("Button", ignoreCase = true) ||
                className.contains("TextView", ignoreCase = true) ||
                className.contains("EditText", ignoreCase = true) ||
                className.contains("ImageView", ignoreCase = true) ||
                className.contains("RecyclerView", ignoreCase = true) ||
                className.contains("ListView", ignoreCase = true) ||
                className.contains("TabHost", ignoreCase = true) ||
                className.contains("ViewPager", ignoreCase = true) ||
                className.contains("LinearLayout", ignoreCase = true) ||
                className.contains("FrameLayout", ignoreCase = true) ||
                className.contains("RelativeLayout", ignoreCase = true) ||
                className.contains("ConstraintLayout", ignoreCase = true) ||
                className.contains("ScrollView", ignoreCase = true) ||
                className.contains("NestedScrollView", ignoreCase = true) ||
                className.contains("CardView", ignoreCase = true) ||
                className.contains("MaterialCardView", ignoreCase = true) ||
                className.contains("ViewGroup", ignoreCase = true) ||
                className.contains("View", ignoreCase = true)
    }
    
    /**
     * 檢查頂層頁面，處理設定頁特例邏輯
     * 若偵測到設定頁且有子畫面，則返回子畫面容器作為新的根節點
     */
    private fun inspectTopPage(root: AccessibilityNodeInfo): AccessibilityNodeInfo {
        try {
            Log.d(TAG, "🔍 開始檢查頂層頁面...")
            
            // 1. 檢查是否有 header_title == "設定"
            val settingsHeader = findHeaderWithTitle(root, "設定")
            if (settingsHeader == null) {
                Log.d(TAG, "未找到設定頁標題，使用原始根節點")
                return root
            }
            
            Log.d(TAG, "✅ 找到設定頁標題")
            
            // 2. 檢查是否有設定清單的徵兆
            val hasSettingList = hasSettingListIndicators(root)
            if (!hasSettingList) {
                Log.d(TAG, "未找到設定清單徵兆，使用原始根節點")
                return root
            }
            
            Log.d(TAG, "✅ 找到設定清單徵兆")
            
            // 3. 掃描容器內是否還有其他 header_title
            val otherHeaders = findAllHeaders(root)
            val nonSettingsHeaders = otherHeaders.filter { header ->
                val text = header.text?.toString()?.trim()
                text != null && text != "設定" && text.isNotBlank()
            }
            
            if (nonSettingsHeaders.isEmpty()) {
                Log.d(TAG, "未找到其他標題，使用原始根節點")
                return root
            }
            
            Log.d(TAG, "✅ 找到 ${nonSettingsHeaders.size} 個非設定標題")
            
            // 4. 取文字 ≠ "設定" 且 bottom 最大的 header_title 當作子畫面 header
            val subPageHeader = findBottomMostHeader(nonSettingsHeaders)
            if (subPageHeader == null) {
                Log.d(TAG, "無法找到子畫面標題，使用原始根節點")
                return root
            }
            
            val subPageTitle = subPageHeader.text?.toString()?.trim() ?: "Unknown"
            Log.d(TAG, "✅ 找到子畫面標題: $subPageTitle")
            
            // 5. 從該 header 往上找最近的「頁面容器」（同時含 header 與 scrollable）
            val pageContainer = findPageContainerFromHeader(subPageHeader)
            if (pageContainer == null) {
                Log.d(TAG, "無法找到頁面容器，使用原始根節點")
                return root
            }
            
            Log.d(TAG, "✅ 找到子畫面容器，切換到子畫面: $subPageTitle")
            return pageContainer
            
        } catch (e: Exception) {
            Log.e(TAG, "檢查頂層頁面時發生錯誤", e)
            return root
        }
    }
    
    /**
     * 尋找指定標題的 header
     */
    private fun findHeaderWithTitle(root: AccessibilityNodeInfo, title: String): AccessibilityNodeInfo? {
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(root)
        
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            
            val viewId = node.viewIdResourceName?.lowercase() ?: ""
            val text = node.text?.toString()?.trim() ?: ""
            
            // 檢查是否為 header_title
            if ((viewId.contains("header_title") || viewId.contains("title") || viewId.contains("header")) 
                && text == title) {
                return node
            }
            
            // 檢查子節點
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }
        
        return null
    }
    
    /**
     * 檢查是否有設定清單的徵兆
     */
    private fun hasSettingListIndicators(root: AccessibilityNodeInfo): Boolean {
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(root)
        
        var settingListCount = 0
        var settingTitleCount = 0
        
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            
            val viewId = node.viewIdResourceName?.lowercase() ?: ""
            val className = node.className?.toString()?.lowercase() ?: ""
            
            // 檢查 id 含 setting_list 的 RecyclerView
            if (viewId.contains("setting_list") && className.contains("recyclerview")) {
                settingListCount++
            }
            
            // 檢查大量 id=setting_title 的列
            if (viewId.contains("setting_title")) {
                settingTitleCount++
            }
            
            // 檢查子節點
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }
        
        val hasIndicators = settingListCount > 0 || settingTitleCount >= 3
        Log.d(TAG, "設定清單徵兆檢查: setting_list=$settingListCount, setting_title=$settingTitleCount, 結果=$hasIndicators")
        
        return hasIndicators
    }
    
    /**
     * 尋找所有 header
     */
    private fun findAllHeaders(root: AccessibilityNodeInfo): List<AccessibilityNodeInfo> {
        val headers = mutableListOf<AccessibilityNodeInfo>()
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(root)
        
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            
            val viewId = node.viewIdResourceName?.lowercase() ?: ""
            val text = node.text?.toString()?.trim()
            
            // 檢查是否為 header
            if ((viewId.contains("header_title") || viewId.contains("title") || viewId.contains("header")) 
                && !text.isNullOrBlank()) {
                headers.add(node)
            }
            
            // 檢查子節點
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }
        
        return headers
    }
    
    /**
     * 找到 bottom 最大的 header（最下方的標題）
     */
    private fun findBottomMostHeader(headers: List<AccessibilityNodeInfo>): AccessibilityNodeInfo? {
        if (headers.isEmpty()) return null
        
        return headers.maxByOrNull { header ->
            val rect = Rect()
            header.getBoundsInScreen(rect)
            rect.bottom
        }
    }
    
    /**
     * 從 header 往上找最近的頁面容器（同時含 header 與 scrollable）
     */
    private fun findPageContainerFromHeader(header: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var current = header.parent
        
        while (current != null) {
            // 檢查是否同時包含 header 和 scrollable 元素
            if (hasHeaderAndScrollable(current)) {
                return current
            }
            current = current.parent
        }
        
        return null
    }
    
    /**
     * 檢查節點是否同時包含 header 和 scrollable 元素
     */
    private fun hasHeaderAndScrollable(node: AccessibilityNodeInfo): Boolean {
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(node)
        
        var hasHeader = false
        var hasScrollable = false
        
        while (queue.isNotEmpty()) {
            val currentNode = queue.removeFirst()
            
            val viewId = currentNode.viewIdResourceName?.lowercase() ?: ""
            val className = currentNode.className?.toString()?.lowercase() ?: ""
            
            // 檢查是否有 header
            if (viewId.contains("header") || viewId.contains("title")) {
                hasHeader = true
            }
            
            // 檢查是否有 scrollable 元素
            if (currentNode.isScrollable || className.contains("scroll") || className.contains("recycler")) {
                hasScrollable = true
            }
            
            // 如果兩者都有，直接返回
            if (hasHeader && hasScrollable) {
                return true
            }
            
            // 檢查子節點
            for (i in 0 until currentNode.childCount) {
                currentNode.getChild(i)?.let { queue.add(it) }
            }
        }
        
        return false
    }
    
    // 判斷是否處於 LINE 設定相關的上下文
    private fun isSettingsContext(root: AccessibilityNodeInfo): Boolean {
        return try {
            // 1) 有 header_title == 設定
            findHeaderWithTitle(root, "設定") != null ||
            // 2) 有 setting_list / setting_title 等設定頁徵兆
            hasSettingListIndicators(root)
        } catch (_: Throwable) {
            false
        }
    }

    // 判斷是否處於 LINE 主頁（home）上下文
    private fun isHomeContext(root: AccessibilityNodeInfo): Boolean {
        return try {
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(root)
            var hits = 0
            while (queue.isNotEmpty() && hits < 2) {
                val node = queue.removeFirst()
                val id = node.viewIdResourceName?.lowercase() ?: ""
                val cls = node.className?.toString()?.lowercase() ?: ""
                if (
                    id.contains("home_tab_") ||
                    id.contains("bnb_button_clickable_area") ||
                    id.contains("main_tab_search_bar") ||
                    id.contains("home_tab_recycler_view") ||
                    id.contains("home_tab_list_container") ||
                    (cls.contains("viewpager") && id.contains("viewpager"))
                ) {
                    hits++
                }
                for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
            }
            hits >= 2
        } catch (_: Throwable) {
            false
        }
    }

    // 判斷是否聊天分頁被選中（首頁底部分頁）
    private fun isChatTabSelected(root: AccessibilityNodeInfo): Boolean {
        return try {
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(root)
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                val id = node.viewIdResourceName?.lowercase() ?: ""
                val text = node.text?.toString()?.trim()?.lowercase() ?: ""
                val desc = node.contentDescription?.toString()?.trim()?.lowercase() ?: ""
                val className = node.className?.toString()?.lowercase() ?: ""
                val isSelected = node.isSelected
                if (
                    id.contains("bnb_button_clickable_area") &&
                    (
                        isSelected ||
                        text.contains("勾選") || desc.contains("勾選")
                    ) &&
                    (text.contains("聊天") || text.contains("chat") || desc.contains("聊天") || desc.contains("chat"))
                ) {
                    return true
                }
                // 某些版本只在分頁容器上標 selected，不含文字
                if (id.contains("bnb_button_clickable_area") && isSelected && className.contains("view")) {
                    // 較寬鬆：若同層附近存在聊天清單容器，亦可視為聊天分頁
                    // 這裡簡化：直接返回 true，避免漏判
                    return true
                }
                for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
            }
            false
        } catch (_: Throwable) {
            false
        }
    }

    // 判斷是否主頁分頁被選中
    private fun isHomeTabSelected(root: AccessibilityNodeInfo): Boolean {
        return try {
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(root)
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                val id = node.viewIdResourceName?.lowercase() ?: ""
                val text = node.text?.toString()?.trim()?.lowercase() ?: ""
                val desc = node.contentDescription?.toString()?.trim()?.lowercase() ?: ""
                val className = node.className?.toString()?.lowercase() ?: ""
                val isSelected = node.isSelected
                if (
                    id.contains("bnb_button_clickable_area") &&
                    (
                        isSelected ||
                        text.contains("勾選") || desc.contains("勾選")
                    ) &&
                    (text.contains("主頁") || text.contains("home") || desc.contains("主頁") || desc.contains("home"))
                ) {
                    return true
                }
                if (id.contains("bnb_button_clickable_area") && isSelected && className.contains("view")) {
                    return true
                }
                for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
            }
            false
        } catch (_: Throwable) {
            false
        }
    }

    // 判斷是否處於聊天上下文（主列表頁存在聊天清單/標題）
    private fun isChatContext(root: AccessibilityNodeInfo): Boolean {
        return try {
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(root)
            var hasChatList = false
            var hasChatTitle = false
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                val id = node.viewIdResourceName?.lowercase() ?: ""
                val text = node.text?.toString()?.trim() ?: ""
                val cls = node.className?.toString()?.lowercase() ?: ""
                if (
                    id.contains("chat_list_recycler_view") ||
                    id.contains("chat_list_view_pager") ||
                    (cls.contains("recyclerview") && id.contains("chat"))
                ) {
                    hasChatList = true
                }
                if (text == "聊天") {
                    hasChatTitle = true
                }
                for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
            }
            // 嚴格：需要有聊天清單，且聊天分頁勾選或標題為「聊天」
            hasChatList && (isChatTabSelected(root) || hasChatTitle)
        } catch (_: Throwable) {
            false
        }
    }
    
    /**
     * 掃描主頁內容，特別關注 header_title 等主頁元素
     */
    private fun findMainPageContent(root: AccessibilityNodeInfo, items: MutableList<String>) {
        try {
            Log.d(TAG, "🔍 開始掃描主頁內容...")
            
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(root)
            
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                
                val text = node.text?.toString()?.trim()
                val contentDesc = node.contentDescription?.toString()?.trim()
                val hint = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    node.hintText?.toString()?.trim()
                } else null
                val viewId = node.viewIdResourceName
                val className = node.className?.toString()
                
                val rect = Rect()
                node.getBoundsInScreen(rect)
                
                val hasText = !text.isNullOrBlank() || !contentDesc.isNullOrBlank() || !hint.isNullOrBlank()
                val isVisible = rect.width() > 0 && rect.height() > 0
                
                // 特別關注主頁的重要元素
                val isMainPageElement = when {
                    // header_title 元素
                    viewId?.contains("header_title") == true -> true
                    // 搜尋欄提示文字
                    viewId?.contains("search_bar_hint") == true -> true
                    // 主要標題
                    viewId?.contains("main_title") == true -> true
                    // 工具列元素
                    viewId?.contains("toolbar") == true -> true
                    // 導航元素
                    viewId?.contains("navigation") == true -> true
                    // 有文字且位置在頂部的元素
                    hasText && rect.top < 300 -> true
                    else -> false
                }
                
                if (isVisible && (hasText || isMainPageElement)) {
                    val displayText = text ?: contentDesc ?: hint ?: "(no text)"
                    
                    val interactions = mutableListOf<String>()
                    if (node.isClickable) interactions.add("clickable")
                    if (node.isEditable) interactions.add("editable")
                    if (node.isScrollable) interactions.add("scrollable")
                    if (node.isSelected) interactions.add("selected")
                    if (node.isLongClickable) interactions.add("longClickable")
                    if (node.isFocused) interactions.add("focused")
                    
                    val label = buildString {
                        append("• \"$displayText\"")
                        if (!viewId.isNullOrBlank()) {
                            append("  [id=$viewId]")
                        }
                        if (!className.isNullOrBlank()) {
                            val shortClass = className.substringAfterLast(".")
                            append("  <$shortClass>")
                        }
                        if (interactions.isNotEmpty()) append("  {${interactions.joinToString(",")}}")
                        append("  @(${rect.left},${rect.top},${rect.width()}x${rect.height()})")
                    }
                    
                    // 將主頁元素插入到列表開頭，優先顯示
                    items.add(0, label)
                    Log.d(TAG, "✅ 找到主頁元素: $displayText")
                }
                
                // 檢查子節點
                for (i in 0 until node.childCount) {
                    node.getChild(i)?.let { queue.add(it) }
                }
            }
            
            Log.d(TAG, "✅ 主頁內容掃描完成，找到 ${items.size} 個元素")
            
        } catch (e: Exception) {
            Log.e(TAG, "掃描主頁內容時發生錯誤", e)
        }
    }
    
    private fun buildLineSpecificSummary(root: AccessibilityNodeInfo): String {
        val items = mutableListOf<String>()
        
        try {
            Log.d(TAG, "Building LINE specific summary...")
            
            // 設定頁特例邏輯：檢查是否為設定頁並處理子畫面（初步）
            val processedRoot = inspectTopPage(root)

            // 僅在「設定相關頁面」時，才使用子畫面容器對焦
            var scanRoot = processedRoot
            if (isSettingsContext(root) || isSettingsContext(processedRoot)) {
                selectBestHeaderTitle(processedRoot, root)?.let { header ->
                    findPageContainerFromHeader(header)?.let { container ->
                        scanRoot = container
                    }
                }
            }

            // 識別當前頁面類型（同時參考 scanRoot 與原始 root，以免漏掉在容器外的 toolbar 標題）
            val currentPageType = identifyLinePageType(scanRoot, root)
            // 除錯：僅列印當前容器的 header_title 候選，避免混淆
            logAllHeaderTitles(scanRoot, label = "scanRoot")
            val currentPageTitle = extractCurrentPageTitle(scanRoot)
            
            // 專門查找 LINE 中的所有可見內容（只掃描選定容器，避免上一頁內容）
            findLineContent(scanRoot, items, 0, maxDepth = 30)
            
            // 若切換到子畫面，避免掃描上一頁的元素，避免混淆
            // 不再額外掃描原始 root（主頁）內容
            
            Log.d(TAG, "Found ${items.size} LINE content items")
            
            // 根據當前頁面類型過濾相關內容
            val filteredItems = filterItemsByPageType(items, currentPageType)
            
            // 按重要性排序內容
            val sortedItems = filteredItems.sortedBy { item ->
                when {
                    item.contains("clickable") && !item.contains("(no text)") -> 0  // 可點擊元素優先
                    item.contains("editable") -> 1  // 可編輯元素
                    item.contains("TextView") && !item.contains("(no text)") -> 2  // 有文字的TextView
                    item.contains("ImageView") -> 3  // 圖片元素
                    item.contains("Button") -> 4  // 按鈕元素
                    item.contains("scrollable") -> 5  // 可滾動元素
                    item.contains("selected") -> 6  // 選中狀態
                    item.contains("focused") -> 7  // 焦點狀態
                    else -> 8
                }
            }
            
            // 分類不同類型的內容
            val clickableItems = sortedItems.filter { it.contains("clickable") && !it.contains("(no text)") }
            val textItems = sortedItems.filter { it.contains("TextView") && !it.contains("(no text)") }
            val imageItems = sortedItems.filter { it.contains("ImageView") }
            val buttonItems = sortedItems.filter { it.contains("Button") }
            val otherItems = sortedItems.filter { 
                !clickableItems.contains(it) && !textItems.contains(it) && 
                !imageItems.contains(it) && !buttonItems.contains(it)
            }
            
            return if (sortedItems.isNotEmpty()) {
                buildString {
                    // 頁面信息頭部
                    append("📱 LINE 頁面信息\n")
                    append("頁面標題: $currentPageTitle\n")
                    append("掃描項目: ${sortedItems.size} 個 (已過濾)\n\n")
                    
                    append("🎯 === 當前頁面內容分析 ===\n")
                    
                    // 可點擊元素（按鈕、選單等）
                    if (clickableItems.isNotEmpty()) {
                        append("\n🖱️ === 可點擊元素 (${clickableItems.size} 項) ===\n")
                        append(clickableItems.take(15).joinToString("\n"))
                        if (clickableItems.size > 15) {
                            append("\n... 還有 ${clickableItems.size - 15} 個可點擊元素\n")
                        }
                    }
                    
                    // 文字內容
                    if (textItems.isNotEmpty()) {
                        append("\n📝 === 文字內容 (${textItems.size} 項) ===\n")
                        append(textItems.take(20).joinToString("\n"))
                        if (textItems.size > 20) {
                            append("\n... 還有 ${textItems.size - 20} 個文字元素\n")
                        }
                    }
                    
                    // 圖片元素
                    if (imageItems.isNotEmpty()) {
                        append("\n🖼️ === 圖片元素 (${imageItems.size} 項) ===\n")
                        append(imageItems.take(10).joinToString("\n"))
                        if (imageItems.size > 10) {
                            append("\n... 還有 ${imageItems.size - 10} 個圖片元素\n")
                        }
                    }
                    
                    // 按鈕元素
                    if (buttonItems.isNotEmpty()) {
                        append("\n🔘 === 按鈕元素 (${buttonItems.size} 項) ===\n")
                        append(buttonItems.take(10).joinToString("\n"))
                        if (buttonItems.size > 10) {
                            append("\n... 還有 ${buttonItems.size - 10} 個按鈕元素\n")
                        }
                    }
                    
                    // 其他元素（只顯示重要的）
                    val importantOtherItems = otherItems.filter { 
                        it.contains("scrollable") || it.contains("selected") || it.contains("focused")
                    }
                    if (importantOtherItems.isNotEmpty()) {
                        append("\n🔧 === 重要其他元素 (${importantOtherItems.size} 項) ===\n")
                        append(importantOtherItems.take(8).joinToString("\n"))
                        if (importantOtherItems.size > 8) {
                            append("\n... 還有 ${importantOtherItems.size - 8} 個重要元素\n")
                        }
                    }
                    
                    // 添加頁面特定的信息（動態生成 + 主頁/聊天頁面專屬文案）
                    val inSettings = isSettingsContext(scanRoot)
                    val inHome = isHomeContext(scanRoot)
                    val chatSelected = isChatTabSelected(scanRoot)
                    val homeSelected = isHomeTabSelected(scanRoot)
                    val inChat = isChatContext(scanRoot)
                    val displayPageType = when {
                        // 底部分頁優先：明確顯示聊天或主頁
                        inHome && !inSettings && chatSelected -> "聊天頁面"
                        inHome && !inSettings && homeSelected -> "主頁"
                        // 其次：內容型判斷（有聊天清單且分頁或標題符合）
                        inChat -> "聊天頁面"
                        inHome && !inSettings -> "主頁"
                        currentPageType == "聊天設定" -> "聊天頁面"
                        else -> currentPageType
                    }

                    append("\n📱 === $displayPageType ===\n")
                    
                    if (displayPageType == "主頁") {
                        append("當前在 LINE 主頁，可瀏覽個人資訊、好友/群組、官方帳號等\n")
                        append("主要元素：搜尋列、我的最愛、好友/群組清單、底部分頁\n")
                    } else if (displayPageType == "聊天頁面") {
                        append("當前在聊天列表頁面，可以查看最近對話與未讀訊息\n")
                        append("主要元素：搜尋列、聊天清單、未讀徽章、分頁切換\n")
                    } else if (inSettings) {
                        if (displayPageType == "設定主頁") {
                            append("當前在 LINE 設定主頁，可以選擇各種設定類別\n")
                            append("主要設定類別：個人檔案、聊天、貼圖、字型、隱私等\n")
                        } else if (displayPageType.endsWith("設定")) {
                            val settingName = displayPageType.removeSuffix("設定")
                            append("當前在${settingName}設定頁面，可以調整${settingName}相關的設定\n")
                            append("主要設定項目：${settingName}相關的各種配置選項\n")
                        } else {
                            append("當前在 $displayPageType 頁面\n")
                            append("可以查看和調整相關的設定選項\n")
                        }
                    } else {
                        // 非設定頁面的描述（泛用）
                        append("當前在 $displayPageType\n")
                    }
                }
            } else {
                "No LINE content detected - trying alternative scan..."
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "Error building LINE specific summary", e)
            return "Error scanning LINE content: ${e.message}"
        }
    }
    
    /**
     * 根據頁面類型過濾相關內容
     */
    private fun filterItemsByPageType(items: List<String>, pageType: String): List<String> {
        return when (pageType) {
            "Chat Settings" -> {
                // 聊天設定頁面：只顯示聊天相關的設定項目
                items.filter { item ->
                    val text = item.lowercase()
                    text.contains("聊天") || text.contains("chat") ||
                    text.contains("背景") || text.contains("background") ||
                    text.contains("字體") || text.contains("font") ||
                    text.contains("字型") || text.contains("傳送") ||
                    text.contains("send") || text.contains("預覽") ||
                    text.contains("preview") || text.contains("設定") ||
                    text.contains("setting") || text.contains("description") ||
                    text.contains("說明") || text.contains("inlined_value")
                }
            }
            "Profile Settings" -> {
                // 個人檔案設定頁面：只顯示個人相關的設定項目
                items.filter { item ->
                    val text = item.lowercase()
                    text.contains("個人") || text.contains("profile") ||
                    text.contains("帳號") || text.contains("account") ||
                    text.contains("隱私") || text.contains("privacy") ||
                    text.contains("貼圖") || text.contains("sticker") ||
                    text.contains("字型") || text.contains("font") ||
                    text.contains("提醒") || text.contains("reminder") ||
                    text.contains("照片") || text.contains("photo") ||
                    text.contains("影片") || text.contains("video") ||
                    text.contains("聊天") || text.contains("chat") ||
                    text.contains("通話") || text.contains("call") ||
                    text.contains("相簿") || text.contains("album") ||
                    text.contains("設定") || text.contains("setting") ||
                    text.contains("title") || text.contains("description")
                }
            }
            "Privacy Settings" -> {
                // 隱私設定頁面：只顯示隱私相關的設定項目
                items.filter { item ->
                    val text = item.lowercase()
                    text.contains("隱私") || text.contains("privacy") ||
                    text.contains("設定") || text.contains("setting") ||
                    text.contains("權限") || text.contains("permission")
                }
            }
            "General Settings" -> {
                // 一般設定頁面：只顯示一般相關的設定項目
                items.filter { item ->
                    val text = item.lowercase()
                    text.contains("一般") || text.contains("general") ||
                    text.contains("設定") || text.contains("setting") ||
                    text.contains("基本") || text.contains("basic")
                }
            }
            "Account Settings" -> {
                // 帳號設定頁面：只顯示帳號相關的設定項目
                items.filter { item ->
                    val text = item.lowercase()
                    text.contains("帳號") || text.contains("account") ||
                    text.contains("設定") || text.contains("setting") ||
                    text.contains("登入") || text.contains("login") ||
                    text.contains("登出") || text.contains("logout")
                }
            }
            else -> {
                // 未知頁面：顯示所有內容
                items
            }
        }
    }
    
    private fun findLineContent(node: AccessibilityNodeInfo, items: MutableList<String>, depth: Int, maxDepth: Int) {
        if (depth > maxDepth) return
        
        try {
            val text = node.text?.toString()?.trim()
            val contentDesc = node.contentDescription?.toString()?.trim()
            val hint = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                node.hintText?.toString()?.trim()
            } else null
            val viewId = node.viewIdResourceName
            val className = node.className?.toString()
            
            val rect = Rect()
            node.getBoundsInScreen(rect)
            
            val hasText = !text.isNullOrBlank() || !contentDesc.isNullOrBlank() || !hint.isNullOrBlank()
            val isInteractive = node.isClickable || node.isEditable || node.isCheckable
            val isImportantContainer = isImportantLineContainer(viewId, className, rect)
            
            // 更寬鬆的可見性檢查，抓取更多元素
            val isVisible = rect.width() > 0 && rect.height() > 0
            
            // 更積極地捕獲內容，降低門檻
            if (isVisible && (hasText || isInteractive || isImportantContainer || depth < 10 || rect.width() > 10 || rect.height() > 10)) {
                val displayText = text ?: contentDesc ?: hint ?: "(no text)"
                
                val interactions = mutableListOf<String>()
                if (node.isClickable) interactions.add("clickable")
                if (node.isEditable) interactions.add("editable")
                if (node.isScrollable) interactions.add("scrollable")
                if (node.isSelected) interactions.add("selected")
                if (node.isLongClickable) interactions.add("longClickable")
                if (node.isFocused) interactions.add("focused")
                
                val label = buildString {
                    append("${"  ".repeat(depth)}• \"$displayText\"")
                    if (!viewId.isNullOrBlank()) {
                        val shortId = viewId.substringAfterLast("/")
                        append("  [id=$shortId]")
                    }
                    if (!className.isNullOrBlank()) {
                        val shortClass = className.substringAfterLast(".")
                        append("  <$shortClass>")
                    }
                    if (interactions.isNotEmpty()) append("  {${interactions.joinToString(",")}}")
                    append("  @(${rect.left},${rect.top},${rect.width()}x${rect.height()})")
                }
                items.add(label)
            }
            
            // 遞歸搜索子節點
            for (i in 0 until node.childCount) {
                val child = node.getChild(i)
                child?.let { findLineContent(it, items, depth + 1, maxDepth) }
            }
            
        } catch (e: Exception) {
            Log.w(TAG, "Error processing node at depth $depth", e)
        }
    }
    
    private fun isImportantLineContainer(viewId: String?, className: String?, rect: Rect): Boolean {
        val id = viewId?.lowercase() ?: ""
        val cls = className?.lowercase() ?: ""
        
        val isGeneralContainer = id.contains("list") || id.contains("recycler") || id.contains("scroll") ||
                cls.contains("recyclerview") || cls.contains("listview") || cls.contains("scrollview") ||
                cls.contains("layout") || cls.contains("view") || cls.contains("group")
        
        return isGeneralContainer && rect.width() > 20 && rect.height() > 20
    }
    
    private fun tryGetDataFromAllWindows() {
        try {
            Log.d(TAG, "Trying to get data from all windows...")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                val windows = windows
                Log.d(TAG, "Found ${windows?.size ?: 0} windows")
                
                // 優先尋找 LINE 視窗
                var lineWindowFound = false
                windows?.forEach { windowInfo ->
                    val root = windowInfo.root
                    if (root != null) {
                        val packageName = root.packageName?.toString()
                        Log.d(TAG, "Processing window: ${windowInfo.title}, Package: $packageName")
                        
                        // 忽略我們自己的視窗
                        if (packageName == "com.example.bubbleassistant") {
                            Log.d(TAG, "忽略 GrandmaHelper 視窗")
                            return@forEach
                        }
                        
                        // 優先處理 LINE 視窗
                        if (packageName == "jp.naver.line.android") {
                            Log.d(TAG, "找到 LINE 視窗，進行深度掃描")
                            lineWindowFound = true
                            val lineContentSummary = buildLineSpecificSummary(root)
                            if (lineContentSummary.isNotEmpty() && !lineContentSummary.contains("No LINE content detected")) {
                                updateLatestScreenInfo(lineContentSummary)
                                updateOverlay(lineContentSummary)
                                return@forEach
                            }
                        }
                    }
                }
                
                // 如果沒有找到 LINE 視窗，尋找其他非 GrandmaHelper 視窗
                if (!lineWindowFound) {
                    windows?.forEach { windowInfo ->
                        val root = windowInfo.root
                        if (root != null) {
                            val packageName = root.packageName?.toString()
                            if (packageName != "com.example.bubbleassistant") {
                                Log.d(TAG, "處理非 LINE 視窗: ${windowInfo.title}")
                                val summary = buildNodeSummary(root, maxItems = 50)
                                if (summary.contains("Captured elements:") && !summary.contains("Captured elements: 0")) {
                                    updateLatestScreenInfo("Other App:\n$summary")
                                    updateOverlay("Other App:\n$summary")
                                    return@forEach
                                }
                            }
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error getting data from all windows", e)
        }
    }
    
    /**
     * 提取當前頁面標題
     */
    private fun extractCurrentPageTitle(rootNode: AccessibilityNodeInfo): String {
        try {
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(rootNode)
            
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                
                // 檢查是否為頁面標題
                val viewId = node.viewIdResourceName?.lowercase() ?: ""
                val text = node.text?.toString()?.trim() ?: ""
                
                if (viewId.contains("title") || viewId.contains("header") || 
                    viewId.contains("toolbar") || viewId.contains("action_bar")) {
                    if (text.isNotBlank()) {
                        return text
                    }
                }
                
                // 檢查子節點
                for (i in 0 until node.childCount) {
                    node.getChild(i)?.let { queue.add(it) }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error extracting page title", e)
        }
        
        return "Unknown Page"
    }
    
    /**
     * 識別 LINE 頁面類型（動態方式）
     */
    private fun identifyLinePageType(rootNode: AccessibilityNodeInfo, originalRoot: AccessibilityNodeInfo? = null): String {
        try {
            Log.d(TAG, "🔍 開始動態識別頁面類型...")
            
            // 首先檢查是否有子畫面的 header_title
            val subPageHeader = selectBestHeaderTitle(rootNode, originalRoot)
            if (subPageHeader != null) {
                val subPageTitle = subPageHeader.text?.toString()?.trim() ?: ""
                Log.d(TAG, "✅ 找到子畫面標題: $subPageTitle")
                
                // 動態生成頁面類型：直接使用 header_title 的內容 + "設定"
                val pageType = "${subPageTitle}設定"
                Log.d(TAG, "✅ 生成頁面類型: $pageType")
                return pageType
            }
            
            Log.d(TAG, "⚠️ 未找到子畫面標題，開始掃描所有 header_title...")
            
            // 若未找到子畫面標題，後續會檢查「設定主頁」

            // 如果沒有子畫面標題，檢查是否為設定主頁
            val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
            queue.add(rootNode)
            
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                
                val viewId = node.viewIdResourceName?.lowercase() ?: ""
                val text = node.text?.toString()?.trim() ?: ""
                
                // 檢查是否為設定主頁
                if (viewId.contains("header_title") && text == "設定") {
                    Log.d(TAG, "✅ 識別為設定主頁")
                    return "設定主頁"
                }
                
                // 檢查其他頁面類型（動態方式）
                if (viewId.contains("header_title") && text.isNotBlank()) {
                    Log.d(TAG, "✅ 找到其他 header_title: $text")
                    val pageType = "${text}設定"
                    Log.d(TAG, "✅ 生成頁面類型: $pageType")
                    return pageType
                }
                
                // 檢查子節點
                for (i in 0 until node.childCount) {
                    node.getChild(i)?.let { queue.add(it) }
                }
            }
            
            // 最後再用啟發式找是否為設定主頁（不依賴 viewId）
            findHeaderTitleHeuristic(rootNode, excludeText = null)?.let { header ->
                val title = header.text?.toString()?.trim()
                if (title == "設定") {
                    Log.d(TAG, "✅ 啟發式識別為設定主頁")
                    return "設定主頁"
                }
            }

            // 若 originalRoot 存在，也用於判斷設定主頁
            if (originalRoot != null && originalRoot !== rootNode) {
                findHeaderTitleHeuristic(originalRoot, excludeText = null)?.let { header ->
                    val title = header.text?.toString()?.trim()
                    if (title == "設定") {
                        Log.d(TAG, "✅ 原始 root 啟發式識別為設定主頁")
                        return "設定主頁"
                    }
                }
            }

            Log.d(TAG, "⚠️ 未找到任何 header_title")
        } catch (e: Exception) {
            Log.e(TAG, "Error identifying page type", e)
        }
        
        return "未知頁面"
    }
    
    /**
     * 找到子畫面的 header_title（非"設定"的 header_title）
     */
    private fun findSubPageHeader(rootNode: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(rootNode)
        
        Log.d(TAG, "🔍 開始搜尋子畫面 header_title...")
        
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            
            val viewId = node.viewIdResourceName?.lowercase() ?: ""
            val text = node.text?.toString()?.trim() ?: ""
            
            // 記錄所有找到的 header_title
            if (viewId.contains("header_title")) {
                Log.d(TAG, "📍 找到 header_title: '$text' [id=$viewId]")
            }
            
            // 找到非"設定"的 header_title
            if (viewId.contains("header_title") && text != "設定" && text.isNotBlank()) {
                Log.d(TAG, "✅ 找到子畫面 header_title: '$text'")
                return node
            }
            
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }
        
        // 如果透過 viewId 未找到，改用啟發式在頂部尋找
        findHeaderTitleHeuristic(rootNode, excludeText = "設定")?.let { header ->
            Log.d(TAG, "✅ 啟發式找到子畫面 header_title: '${header.text}'")
            return header
        }

        Log.d(TAG, "⚠️ 未找到子畫面 header_title")
        return null
    }

    // 使用頂部位置與類別作為啟發式尋找 header_title（不依賴 viewId）
    private fun findHeaderTitleHeuristic(rootNode: AccessibilityNodeInfo, excludeText: String? = null): AccessibilityNodeInfo? {
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(rootNode)

        val candidates: MutableList<Pair<AccessibilityNodeInfo, android.graphics.Rect>> = mutableListOf()
        val rect = android.graphics.Rect()

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()

            val className = node.className?.toString() ?: ""
            val text = node.text?.toString()?.trim()

            if (!text.isNullOrBlank() && className.contains("textview", ignoreCase = true)) {
                node.getBoundsInScreen(rect)
                val top = rect.top
                val height = rect.height()
                // 更嚴格：只考慮螢幕頂部 0~220px、且高度 40~120 的文字
                if (top in 0..220 && height in 40..120) {
                    if (excludeText == null || text != excludeText) {
                        candidates.add(Pair(AccessibilityNodeInfo.obtain(node), android.graphics.Rect(rect)))
                    }
                }
            }

            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }

        if (candidates.isEmpty()) return null

        // 取 bottom 最大者（較接近最上層且實際可見的標題文字）
        val best = candidates.maxByOrNull { it.second.bottom }?.first
        return best
    }

    // 蒐集並從兩個 root 中選出最佳的 header_title（優先 id，其次啟發式；皆排除「設定」；比較 bottom）
    private fun selectBestHeaderTitle(rootNode: AccessibilityNodeInfo, originalRoot: AccessibilityNodeInfo? = null): AccessibilityNodeInfo? {
        val rect = android.graphics.Rect()
        val idCandidates: MutableList<Pair<AccessibilityNodeInfo, Int>> = mutableListOf()
        val heuristicCandidates: MutableList<Pair<AccessibilityNodeInfo, Int>> = mutableListOf()

        fun collect(from: AccessibilityNodeInfo) {
            // 1) 透過 id 精準找
            run {
                val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
                queue.add(from)
                while (queue.isNotEmpty()) {
                    val node = queue.removeFirst()
                    val id = node.viewIdResourceName?.lowercase() ?: ""
                    val text = node.text?.toString()?.trim().orEmpty()
                    if (id.contains("header_title") && text.isNotBlank() && text != "設定") {
                        node.getBoundsInScreen(rect)
                        idCandidates.add(Pair(AccessibilityNodeInfo.obtain(node), rect.bottom))
                    }
                    for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
                }
            }
            // 2) 啟發式補強
            findHeaderTitleHeuristic(from, excludeText = "設定")?.let { h ->
                val t = h.text?.toString()?.trim().orEmpty()
                if (t.isNotBlank()) {
                    h.getBoundsInScreen(rect)
                    heuristicCandidates.add(Pair(AccessibilityNodeInfo.obtain(h), rect.bottom))
                }
            }
        }

        collect(rootNode)
        if (originalRoot != null && originalRoot !== rootNode) collect(originalRoot)

        if (idCandidates.isNotEmpty()) {
            val best = idCandidates.maxByOrNull { it.second }!!.first
            Log.d(TAG, "✅ 最佳 header_title(由 id): '${best.text}' (bottom=${idCandidates.maxOf { it.second }})")
            return best
        }
        if (heuristicCandidates.isNotEmpty()) {
            val best = heuristicCandidates.maxByOrNull { it.second }!!.first
            Log.d(TAG, "✅ 最佳 header_title(啟發式): '${best.text}' (bottom=${heuristicCandidates.maxOf { it.second }})")
            return best
        }
        return null
    }

    // 列印所有 header_title（兩個 root 都列印）
    private fun logAllHeaderTitles(rootNode: AccessibilityNodeInfo, label: String) {
        val rect = android.graphics.Rect()
        val queue: ArrayDeque<AccessibilityNodeInfo> = ArrayDeque()
        queue.add(rootNode)
        Log.d(TAG, "🔎 列印 header_title 候選 [$label] ...")
        var count = 0
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val id = node.viewIdResourceName?.lowercase() ?: ""
            val text = node.text?.toString()?.trim().orEmpty()
            if ((id.contains("header_title") || (node.className?.toString()?.contains("textview", true) == true)) && text.isNotBlank()) {
                node.getBoundsInScreen(rect)
                Log.d(TAG, "📍 [$label] header candidate: '$text' id=$id @(${rect.left},${rect.top},${rect.width()}x${rect.height()})")
                count++
            }
            for (i in 0 until node.childCount) node.getChild(i)?.let { queue.add(it) }
        }
        Log.d(TAG, "🔎 [$label] 總共 ${count} 個候選")
    }
}

