package com.example.bubbleassistant

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.foundation.layout.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.example.bubbleassistant.ui.theme.BubbleAssistantTheme

class MainActivity : ComponentActivity() {

    // 讓廣播/生命週期可更新 UI 的狀態
    private var bubbleOnState: MutableState<Boolean>? = null

    // 讓 onResume() 能強制要求 Compose 顯示「無障礙導引」對話框
    private var accessibilityGuideState: MutableState<Boolean>? = null

    // 接收 BubbleService 廣播，把 UI 開關同步 ON/OFF
    private val stateReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context?, intent: Intent?) {
            if (intent?.action == BubbleService.ACTION_BUBBLE_STATE) {
                val running = intent.getBooleanExtra(BubbleService.EXTRA_RUNNING, false)
                bubbleOnState?.value = running
            }
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // 一進來就檢查懸浮窗；沒有就直接跳設定
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(
                this,
                "請允許本 App 能顯示在最上層",
                Toast.LENGTH_LONG
            ).show()
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        }

        // 監聽泡泡狀態
        ContextCompat.registerReceiver(
            /* context = */ this,
            /* receiver = */ stateReceiver,
            /* filter = */ IntentFilter(BubbleService.ACTION_BUBBLE_STATE),
            /* flags = */ ContextCompat.RECEIVER_NOT_EXPORTED
        )

        // 有懸浮窗權限就預設啟動泡泡（Switch 初值 = ON）
        val defaultOn = if (Settings.canDrawOverlays(this)) {
            startService(Intent(this, BubbleService::class.java))
            true
        } else false

        setContent {
            BubbleAssistantTheme {
                var bubbleOn by remember { mutableStateOf(defaultOn) }
                // 提供給廣播更新的引用
                bubbleOnState = remember { mutableStateOf(bubbleOn) }
                bubbleOn = bubbleOnState!!.value

                // 這個 state 讓 onResume() 也能控制是否顯示對話框
                val showAccessibilityGuide = remember { mutableStateOf(false) }
                accessibilityGuideState = showAccessibilityGuide

                // 只在「進到主畫面後」做一次檢查（不在 onCreate 立刻跳）
                LaunchedEffect(Unit) {
                    if (Settings.canDrawOverlays(this@MainActivity) && !isAccessibilityServiceEnabled()) {
                        showAccessibilityGuide.value = true
                    }
                }

                Scaffold(
                    topBar = { TopAppBar(title = { Text("設定") }) }
                ) { innerPadding ->
                    SettingsScreen(
                        modifier = Modifier.padding(innerPadding),
                        bubbleOn = bubbleOn,
                        onBubbleToggle = { checked ->
                            if (checked) {
                                if (!Settings.canDrawOverlays(this@MainActivity)) {
                                    // 沒有懸浮窗權限 → 要求使用者去開
                                    Toast.makeText(
                                        this@MainActivity,
                                        "請先允許懸浮窗權限",
                                        Toast.LENGTH_SHORT
                                    ).show()
                                    val intent = Intent(
                                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                        Uri.parse("package:$packageName")
                                    )
                                    startActivity(intent)
                                } else {
                                    startService(Intent(this@MainActivity, BubbleService::class.java))
                                    bubbleOnState?.value = true
                                    // 啟動泡泡後若偵測到無障礙未開，也提示一次
                                    if (!isAccessibilityServiceEnabled()) {
                                        showAccessibilityGuide.value = true
                                    }
                                }
                            } else {
                                stopService(Intent(this@MainActivity, BubbleService::class.java))
                                bubbleOnState?.value = false
                            }
                        }
                    )
                }

                // 「螢幕監控服務」導引對話框（沿用：稍後／前往設定）
                if (showAccessibilityGuide.value) {
                    AlertDialog(
                        onDismissRequest = { showAccessibilityGuide.value = false },
                        title = { Text("需要開啟協助工具服務") },
                        text = {
                            Text("請在接下來的畫面中點選『已下載的應用程式』，並找到『BubbleAssistant』將其啟用，以允許螢幕內容分析")
                        },
                        confirmButton = {
                            TextButton(onClick = {
                                showAccessibilityGuide.value = false
                                val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                startActivity(intent)
                            }) { Text("前往設定") }
                        },
                        dismissButton = {
                            TextButton(onClick = { showAccessibilityGuide.value = false }) { Text("稍後") }
                        }
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()

        // 從權限頁返回：若開關是 ON 且懸浮窗已允許 → 啟動服務；否則把開關打回 OFF
        bubbleOnState?.let { state ->
            if (state.value) {
                if (Settings.canDrawOverlays(this)) {
                    startService(Intent(this, BubbleService::class.java))
                } else {
                    state.value = false
                }
            }
        }

        // **關鍵補強**：每次回到主畫面，都再檢查一次；沒開就把對話框打開
        if (Settings.canDrawOverlays(this) && !isAccessibilityServiceEnabled()) {
            accessibilityGuideState?.value = true
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        try { unregisterReceiver(stateReceiver) } catch (_: Exception) {}
        stopService(Intent(this, BubbleService::class.java))
    }

    /**
     * 檢查無障礙服務是否已啟用
     * 注意：service 名稱要和你的 AccessibilityService 實作類（例：ScreenMonitor）相符
     */
    private fun isAccessibilityServiceEnabled(): Boolean {
        val accessibilityEnabled = try {
            Settings.Secure.getInt(contentResolver, Settings.Secure.ACCESSIBILITY_ENABLED, 0)
        } catch (_: Settings.SettingNotFoundException) {
            0
        }
        if (accessibilityEnabled == 1) {
            val service = "${packageName}/${ScreenMonitor::class.java.name}"
            val enabled = Settings.Secure.getString(
                contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            return enabled?.split(':')?.any { it.equals(service, ignoreCase = true) } == true
        }
        return false
    }
}

@Composable
fun SettingsScreen(
    modifier: Modifier = Modifier,
    bubbleOn: Boolean,
    onBubbleToggle: (Boolean) -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Bubble Assistant")
            Switch(checked = bubbleOn, onCheckedChange = onBubbleToggle)
        }
    }
}
