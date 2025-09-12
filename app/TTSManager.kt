// TextToSpeechManager.kt
package com.example.bubbleassistant // 請替換成您的專案套件名稱

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale

class TextToSpeechManager(
    private val context: Context,
    private val onUtteranceDone: (String?) -> Unit = {}
) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var isInitialized = false
    private var lastSpokenText: String? = null

    init {
        tts = TextToSpeech(context, this)
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                // Not used
            }

            override fun onDone(utteranceId: String?) {
                onUtteranceDone(utteranceId)
            }

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                Log.e("TextToSpeechManager", "TTS Error for utteranceId: $utteranceId")
            }
        })
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.TRADITIONAL_CHINESE) // 您可以根據需求更改語言
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.e("TextToSpeechManager", "The Language specified is not supported!")
            } else {
                isInitialized = true
                Log.i("TextToSpeechManager", "TTS Initialized successfully.")
                // 如果在初始化完成前有待播放的文字，可以在這裡播放
                lastSpokenText?.let {
                    speak(it)
                }
            }
        } else {
            Log.e("TextToSpeechManager", "TTS Initialization failed!")
        }
    }

    fun speak(text: String, utteranceId: String = "defaultUtteranceId") {
        if (!isInitialized) {
            lastSpokenText = text // 存儲起來，等待初始化完成後播放
            Log.w("TextToSpeechManager", "TTS not initialized yet. Queuing text: $text")
            return
        }
        if (text.isBlank()) {
            Log.w("TextToSpeechManager", "Text to speak is blank.")
            return
        }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        lastSpokenText = null // 清除已安排播放的文字
        Log.i("TextToSpeechManager", "Speaking: $text")
    }

    fun stop() {
        tts?.stop()
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        isInitialized = false
        Log.i("TextToSpeechManager", "TTS Shutdown.")
    }
}
