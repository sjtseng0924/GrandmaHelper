// TextToSpeechManager.kt
package com.example.bubbleassistant

import android.content.Context
import android.os.Build
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 全 App 單例 TextToSpeech 管理器
 * 使用方法：
 *   TextToSpeechManager.getInstance(context).speak("文字")
 */
class TextToSpeechManager private constructor(private val context: Context) :
    TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var isInitialized = false
    private var lastSpokenText: String? = null

    // 用於確保單例初始化只執行一次
    private val isInitializing = AtomicBoolean(false)

    companion object {
        @Volatile
        private var INSTANCE: TextToSpeechManager? = null

        fun getInstance(context: Context): TextToSpeechManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: TextToSpeechManager(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
    @Volatile
    var voiceEnabled: Boolean = true
        private set

    fun setVoiceEnabled(enabled: Boolean) {
        voiceEnabled = enabled
        Log.i("TextToSpeechManager", "Voice mode set to: $enabled")
    }
    init {
        if (!isInitializing.getAndSet(true)) {
            tts = TextToSpeech(context.applicationContext, this)
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    // 不使用
                }

                override fun onDone(utteranceId: String?) {
                    Log.i("TextToSpeechManager", "Utterance done: $utteranceId")
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    Log.e("TextToSpeechManager", "TTS Error for utteranceId: $utteranceId")
                }
            })
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.TRADITIONAL_CHINESE)
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.e("TextToSpeechManager", "The Language specified is not supported!")
            } else {
                isInitialized = true
                Log.i("TextToSpeechManager", "TTS Initialized successfully.")
                lastSpokenText?.let { speak(it) }
            }
        } else {
            Log.e("TextToSpeechManager", "TTS Initialization failed!")
        }
    }

    /**
     * 播放文字
     * @param text 要播報的文字
     * @param utteranceId 每次播報都產生唯一 ID
     */
    fun speak(text: String, utteranceId: String = "tts_${System.currentTimeMillis()}") {
        if (!voiceEnabled) {
            Log.i("TextToSpeechManager", "Voice mode disabled. Skipping: $text")
            return
        }

        if (!isInitialized) {
            lastSpokenText = text
            Log.w("TextToSpeechManager", "TTS not initialized yet. Queuing text: $text")
            return
        }
        if (text.isBlank()) {
            Log.w("TextToSpeechManager", "Text to speak is blank.")
            return
        }

        val params = Bundle().apply {
            putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId)
        }

        tts?.speak(text, TextToSpeech.QUEUE_ADD, params, utteranceId)
        lastSpokenText = null
        Log.i("TextToSpeechManager", "Speaking: $text with ID: $utteranceId")
    }

    /**
     * 停止播報
     */
    fun stop() {
        tts?.stop()
    }

    /**
     * 釋放資源（整個 App 關閉時再呼叫）
     */
    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        isInitialized = false
        Log.i("TextToSpeechManager", "TTS Shutdown.")
    }
}
