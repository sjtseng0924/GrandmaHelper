package com.example.bubbleassistant

import android.content.Context
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

// 不新增檔案，常數就放這裡
private const val PREFS = "shortcut_prefs"
private const val K1 = "shortcut_1"
private const val K2 = "shortcut_2"
private const val K3 = "shortcut_3"

class FeaturesActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { FeaturesScreen(onBack = { finish() }) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeaturesScreen(
    onBack: () -> Unit
) {
    val ctx = LocalContext.current

    // 三個可編輯文字狀態
    var shortcut1Text by remember { mutableStateOf("傳訊息給兒子") }
    var shortcut2Text by remember { mutableStateOf("打電話給孫女") }
    var shortcut3Text by remember { mutableStateOf("拍照並傳到家庭群組") }

    // 進畫面時載回已儲存的值（若有）
    LaunchedEffect(Unit) {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        p.getString(K1, null)?.let { shortcut1Text = it }
        p.getString(K2, null)?.let { shortcut2Text = it }
        p.getString(K3, null)?.let { shortcut3Text = it }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("常用詢問設定", color = Color.Black) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回", tint = Color(0xFF42A09D))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFFE2F4F3)) // 舊版兼容
            )
        },
        containerColor = Color(0xFFE2F4F3)
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Editable fields
            ShortcutTextField(label = "常用詢問 1", text = shortcut1Text, onTextChange = { shortcut1Text = it })
            ShortcutTextField(label = "常用詢問 2", text = shortcut2Text, onTextChange = { shortcut2Text = it })
            ShortcutTextField(label = "常用詢問 3", text = shortcut3Text, onTextChange = { shortcut3Text = it })

            Spacer(modifier = Modifier.height(24.dp))

            // 儲存按鈕
            Button(
                onClick = {
                    val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    val e = p.edit()

                    fun putOrRemove(key: String, value: String) {
                        val v = value.trim()
                        if (v.isNotEmpty()) e.putString(key, v) else e.remove(key) // 空字串就不要存
                    }

                    putOrRemove(K1, shortcut1Text)
                    putOrRemove(K2, shortcut2Text)
                    putOrRemove(K3, shortcut3Text)

                    val ok = e.commit()
                    Toast.makeText(ctx, if (ok) "已儲存" else "儲存失敗", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF42A09D))
            ) {
                Text("儲存", color = Color.White)
            }
        }
    }
}

@Composable
fun ShortcutTextField(label: String, text: String, onTextChange: (String) -> Unit) {
    OutlinedTextField(
        value = text,
        onValueChange = onTextChange,
        label = { Text(label, color = Color.Black) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        colors = TextFieldDefaults.colors(
            focusedContainerColor = Color.White,       // 原 backgroundColor
            unfocusedContainerColor = Color.White,     // 原 backgroundColor
            focusedIndicatorColor = Color(0xFF42A09D),
            unfocusedIndicatorColor = Color.LightGray,
            cursorColor = Color(0xFF42A09D),
            focusedLabelColor = Color(0xFF42A09D),
            unfocusedLabelColor = Color.Gray           // 可選，給未聚焦時 label 顏色
        )
    )
}
