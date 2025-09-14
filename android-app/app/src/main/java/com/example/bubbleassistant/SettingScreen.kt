package com.example.bubbleassistant

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardVoice
import androidx.compose.material.icons.filled.Tune
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TextField
import androidx.compose.ui.graphics.vector.ImageVector
// --- added imports for image picker, preview, upload, and saving ---
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import androidx.compose.foundation.Image
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.FileOutputStream
import android.provider.MediaStore
import android.content.ContentValues
import android.os.Build
import android.widget.Toast
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
// --- added imports for EXIF orientation ---
import androidx.exifinterface.media.ExifInterface
import android.graphics.Matrix

@Composable
fun SettingsScreen(
    modifier: Modifier = Modifier,
    bubbleOn: Boolean,
    onBubbleToggle: (Boolean) -> Unit,
    voiceOn: Boolean,
    onVoiceToggle: (Boolean) -> Unit,
    onNavigateTutorial: () -> Unit,
    onNavigateFeatures: () -> Unit
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFFE2F4F3)) // 整體背景
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Grandma Helper",
            style = MaterialTheme.typography.headlineLarge,
            color = Color.Black
        )

        // Bubble Assistant 開關
        SettingItemRow(
            icon = Icons.Default.ChatBubble,
            title = "開啟詢問泡泡",
            checked = bubbleOn,
            onCheckedChange = onBubbleToggle
        )

        // 語音開關
        val context = LocalContext.current
        val ttsManager = remember { TextToSpeechManager.getInstance(context) }
        LaunchedEffect(voiceOn) {
            ttsManager.setVoiceEnabled(voiceOn)
        }
        SettingItemRow(
            icon = Icons.Default.KeyboardVoice,
            title = "開啟語音模式",
            checked = voiceOn,
            onCheckedChange = {
                onVoiceToggle(it)
                ttsManager.setVoiceEnabled(it)
            }
        )

        // 常用功能
        SettingNavRow(icon = Icons.Default.Tune, title = "常用詢問設定", onClick = onNavigateFeatures)

        // 使用教學
        SettingNavRow(icon = Icons.Default.Info, title = "App 使用教學", onClick = onNavigateTutorial)

        // 早安圖 - 可展開卡片
        var morningCardExpanded by remember { mutableStateOf(false) }
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                // 標題 Row
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { morningCardExpanded = !morningCardExpanded }
                ) {
                    Icon(
                        imageVector = Icons.Default.Image,
                        contentDescription = "早安圖 Icon",
                        tint = Color(0xFF42A09D),
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("每日一張早安圖", style = MaterialTheme.typography.titleMedium, color = Color.Black, modifier = Modifier.weight(1f))
                    Icon(
                        imageVector = if (morningCardExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = if (morningCardExpanded) "收起" else "展開",
                        tint = Color(0xFF42A09D)
                    )
                }

                // 展開內容
                if (morningCardExpanded) {
                    Spacer(modifier = Modifier.height(16.dp))

                    var prompt by rememberSaveable { mutableStateOf("") }

                    // states
                    var pickedImageUri by rememberSaveable { mutableStateOf<String?>(null) }
                    var previewBitmap by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
                    var resultBitmap by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
                    var isLoading by remember { mutableStateOf(false) }
                    var errorMsg by remember { mutableStateOf<String?>(null) }

                    val scope = rememberCoroutineScope()
                    val pickImageLauncher = rememberLauncherForActivityResult(
                        contract = ActivityResultContracts.GetContent()
                    ) { uri: Uri? ->
                        errorMsg = null
                        resultBitmap = null
                        pickedImageUri = uri?.toString()
                        if (uri != null) {
                            scope.launch {
                                previewBitmap = decodeBitmapWithOrientation(context, uri)
                                    ?: run { errorMsg = "讀取圖片失敗"; null }
                            }
                        } else {
                            previewBitmap = null
                        }
                    }

                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // 可點擊的預覽容器（依比例維持：weight + fillMaxSize）
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxSize()
                                .background(Color(0xFFE2F4F3))
                                .clickable(enabled = !isLoading) { pickImageLauncher.launch("image/*") },
                            contentAlignment = Alignment.Center
                        ) {
                            when {
                                resultBitmap != null -> {
                                    Image(bitmap = resultBitmap!!.asImageBitmap(), contentDescription = "生成結果")
                                }
                                previewBitmap != null -> {
                                    Image(bitmap = previewBitmap!!.asImageBitmap(), contentDescription = "已選擇圖片預覽")
                                }
                                else -> {
                                    Text("點此選擇圖片", color = Color.Gray)
                                }
                            }

                            // 清除按鈕：左上角的小叉叉
                            if (previewBitmap != null || resultBitmap != null) {
                                IconButton(
                                    onClick = {
                                        pickedImageUri = null
                                        previewBitmap = null
                                        resultBitmap = null
                                        errorMsg = null
                                    },
                                    modifier = Modifier.align(Alignment.TopStart)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Close,
                                        contentDescription = "清除圖片",
                                        tint = Color(0xFF333333)
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // prompt 輸入（移除外部的選圖按鈕，改為點擊預覽框啟動）
                            TextField(
                                value = prompt,
                                onValueChange = { prompt = it },
                                placeholder = { Text("想要生成怎樣的早安圖") },
                                singleLine = true,
                                modifier = Modifier
                                    .weight(1f)
                                    .heightIn(min = 56.dp),
                                colors = TextFieldDefaults.colors(
                                    focusedContainerColor = Color.White,
                                    unfocusedContainerColor = Color.White,
                                    focusedIndicatorColor = Color(0xFF42A09D),
                                    unfocusedIndicatorColor = Color.LightGray,
                                    cursorColor = Color(0xFF42A09D),
                                    focusedTextColor = Color.Black,
                                    unfocusedTextColor = Color.Black,
                                    focusedPlaceholderColor = Color.Gray,
                                    unfocusedPlaceholderColor = Color.Gray
                                )
                            )

                            Spacer(modifier = Modifier.width(8.dp))

                            // 生成
                            Button(
                                enabled = pickedImageUri != null && !isLoading,
                                onClick = {
                                    errorMsg = null
                                    val uri = pickedImageUri?.let { Uri.parse(it) } ?: return@Button
                                    scope.launch {
                                        isLoading = true
                                        try {
                                            val generated = uploadAndGenerateOriented(context, uri, prompt)
                                            resultBitmap = generated
                                        } catch (t: Throwable) {
                                            errorMsg = t.message ?: "上傳或生成失敗"
                                        } finally {
                                            isLoading = false
                                        }
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF42A09D))
                            ) {
                                Text(if (isLoading) "生成中..." else "生成", color = Color.White)
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // 另存圖片
                        Button(
                            enabled = resultBitmap != null && !isLoading,
                            onClick = {
                                val bmp = resultBitmap ?: return@Button
                                scope.launch {
                                    val ok = saveBitmapToGallery(
                                        context = context,
                                        bitmap = bmp,
                                        displayName = "morning_image_${System.currentTimeMillis()}.png"
                                    )
                                    Toast.makeText(
                                        context,
                                        if (ok) "已另存到相簿/Pictures/GrandmaHelper" else "儲存失敗",
                                        Toast.LENGTH_SHORT
                                    ).show()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF42A09D))
                        ) {
                            Text("另存圖片", color = Color.White)
                        }

                        if (!errorMsg.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(errorMsg!!, color = Color.Red)
                        }
                    }
                }
            }
        }
    }
}

// 讀取並校正 EXIF 方向
private suspend fun decodeBitmapWithOrientation(
    context: android.content.Context,
    uri: Uri
): android.graphics.Bitmap? = withContext(Dispatchers.IO) {
    try {
        context.contentResolver.openInputStream(uri)?.use { base ->
            val bytes = base.readBytes()
            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return@withContext null
            val orientation = ExifInterface(bytes.inputStream()).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.preScale(-1f, 1f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.preScale(1f, -1f)
                ExifInterface.ORIENTATION_TRANSPOSE -> { matrix.postRotate(90f); matrix.preScale(-1f, 1f) }
                ExifInterface.ORIENTATION_TRANSVERSE -> { matrix.postRotate(270f); matrix.preScale(-1f, 1f) }
                else -> return@withContext bmp
            }
            android.graphics.Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, matrix, true)
        }
    } catch (_: Throwable) {
        null
    }
}

// 上傳（先校正方向後再壓成 JPEG 以避免旋轉問題）
private suspend fun uploadAndGenerateOriented(
    context: android.content.Context,
    uri: Uri,
    prompt: String
): android.graphics.Bitmap = withContext(Dispatchers.IO) {
    val oriented = decodeBitmapWithOrientation(context, uri)
        ?: throw IllegalStateException("無法讀取選擇的圖片")

    val tempFile = File(context.cacheDir, "upload_${System.currentTimeMillis()}.jpg")
    FileOutputStream(tempFile).use { oriented.compress(android.graphics.Bitmap.CompressFormat.JPEG, 95, it) }

    val client = OkHttpClient.Builder().build()
    val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
        .addFormDataPart(
            name = "image",
            filename = tempFile.name,
            body = tempFile.asRequestBody("image/jpeg".toMediaTypeOrNull())
        )
        .addFormDataPart("prompt", if (prompt.isNotBlank()) prompt else "加上平靜感的早安圖")
        .build()

    val request = Request.Builder()
        .url(GEMINI_IMAGE_API_URL)
        .post(multipart)
        .build()

    val bytes = client.newCall(request).execute().use { resp ->
        if (!resp.isSuccessful) throw IllegalStateException("HTTP ${resp.code}")
        resp.body?.bytes() ?: throw IllegalStateException("空回應")
    }

    val outFile = File(context.cacheDir, "edited_${System.currentTimeMillis()}.png")
    FileOutputStream(outFile).use { it.write(bytes) }

    BitmapFactory.decodeFile(outFile.absolutePath) ?: throw IllegalStateException("無法解析回傳圖片")
}

// 儲存到相簿
private suspend fun saveBitmapToGallery(
    context: android.content.Context,
    bitmap: android.graphics.Bitmap,
    displayName: String
): Boolean = withContext(Dispatchers.IO) {
    try {
        val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        }
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, displayName)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/GrandmaHelper")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(collection, values) ?: return@withContext false
        resolver.openOutputStream(uri)?.use { out ->
            val ok = bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out)
            if (!ok) return@withContext false
        } ?: return@withContext false
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        }
        true
    } catch (_: Throwable) {
        false
    }
}

// API endpoint
private const val GEMINI_IMAGE_API_URL: String = "https://morning-image-api-855188038216.asia-east1.run.app/generate"

// 可重複使用的設定開關項目
@Composable
fun SettingItemRow(
    icon: ImageVector,
    title: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White, shape = MaterialTheme.shapes.medium)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color(0xFF42A09D),
            modifier = Modifier.size(24.dp)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Text(
            text = title,
            color = Color.Black,
            modifier = Modifier.weight(1f) // 讓文字佔滿中間空間
        )

        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = Color(0xFF42A09D)
            )
        )
    }
}

// 可點擊導覽的設定列
@Composable
fun SettingNavRow(
    icon: ImageVector,
    title: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .background(Color.White, shape = MaterialTheme.shapes.medium)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color(0xFF42A09D),
            modifier = Modifier.size(24.dp)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Text(
            text = title,
            color = Color.Black,
            modifier = Modifier.weight(1f) // 填滿空間，讓箭頭靠右
        )

        Icon(
            imageVector = Icons.Default.KeyboardArrowRight,
            contentDescription = null,
            tint = Color(0xFF42A09D)
        )
    }
}
