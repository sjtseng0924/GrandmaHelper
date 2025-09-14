package com.example.bubbleassistant

import android.app.Activity
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

class TutorialActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TutorialScreen(onBack = { finish() })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TutorialScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val activity = context as? Activity   // 取得目前的 Activity

    val pages = listOf(
        "打開泡泡的開關",
        "點擊泡泡",
        "輸入問題(也可以點擊上方快速捷徑喔！)",
        "根據步驟操作，完成點擊右上方打勾",
        "問題解決！"
    )

    var currentPage by remember { mutableStateOf(0) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("使用教學") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { inner ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(inner)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            // 卡片顯示教學內容
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f), // 卡片自動佔滿剩餘高度
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(6.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White)
            ) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(pages[currentPage], style = MaterialTheme.typography.titleLarge)
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // 底部控制區
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 左箭頭
                IconButton(
                    onClick = { if (currentPage > 0) currentPage-- },
                    enabled = currentPage > 0
                ) {
                    Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "上一頁")
                }

                // 頁碼指示器
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    pages.forEachIndexed { index, _ ->
                        Box(
                            modifier = Modifier
                                .size(if (index == currentPage) 12.dp else 8.dp)
                                .background(
                                    if (index == currentPage) Color(0xFF42A09D) else Color.Gray,
                                    shape = CircleShape
                                )
                        )
                    }
                }

                // 右箭頭
                IconButton(
                    onClick = { if (currentPage < pages.size - 1) currentPage++ },
                    enabled = currentPage < pages.size - 1
                ) {
                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = "下一頁")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 如果是最後一頁，就顯示「開始操作」按鈕
            if (currentPage == pages.size - 1) {
                Button(
                    onClick = { activity?.finish() }, // 跟返回鍵一樣，直接關閉 TutorialActivity
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF42A09D)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("開始操作", color = Color.White)
                }
            }
        }
    }
}
