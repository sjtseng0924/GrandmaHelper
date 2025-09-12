package com.example.bubbleassistant

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.IBinder
import android.view.*
import android.widget.ImageView
import android.widget.Toast
import android.content.res.Resources

class BubbleService : Service() {
    companion object {
        const val ACTION_BUBBLE_STATE = "com.example.bubbleassistant.BUBBLE_STATE"
        const val EXTRA_RUNNING = "running"
    }
    private lateinit var windowManager: WindowManager
    private lateinit var bubbleView: View
    private lateinit var deleteZoneView: View
    private lateinit var layoutParams: WindowManager.LayoutParams
    private lateinit var deleteZoneParams: WindowManager.LayoutParams

    override fun onCreate() {
        super.onCreate()

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        val inflater = LayoutInflater.from(this)

        // 加入泡泡 View
        bubbleView = inflater.inflate(R.layout.bubble_layout, null)
        layoutParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 100
            y = 300
        }

        // 加入刪除區域 View
        deleteZoneView = inflater.inflate(R.layout.delete_area, null)
        deleteZoneParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            dpToPx(150),
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.BOTTOM
        }

        windowManager.addView(bubbleView, layoutParams)
        windowManager.addView(deleteZoneView, deleteZoneParams)
        // 服務啟動 -> 通知主畫面 Switch 切成 ON
        sendBroadcast(Intent(ACTION_BUBBLE_STATE).putExtra(EXTRA_RUNNING, true).setPackage(packageName))
        deleteZoneView.visibility = View.GONE
        val deleteZoneImage = deleteZoneView.findViewById<ImageView>(R.id.delete_zone)
        deleteZoneImage.visibility = View.GONE

        // 拖曳或點擊泡泡
        bubbleView.setOnTouchListener(object : View.OnTouchListener {
            private var initX = 0
            private var initY = 0
            private var downX = 0f
            private var downY = 0f
            private var isDragging = false

            override fun onTouch(v: View, event: MotionEvent): Boolean {
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initX = layoutParams.x
                        initY = layoutParams.y
                        downX = event.rawX
                        downY = event.rawY
                        isDragging = false
                        deleteZoneView.visibility = View.VISIBLE
                        deleteZoneImage.visibility = View.VISIBLE
                        return true
                    }

                    MotionEvent.ACTION_MOVE -> {
                        val deltaX = event.rawX - downX
                        val deltaY = event.rawY - downY

                        if (Math.abs(deltaX) > 10 || Math.abs(deltaY) > 10) {
                            isDragging = true
                            layoutParams.x = initX + deltaX.toInt()
                            layoutParams.y = initY + deltaY.toInt()
                            windowManager.updateViewLayout(bubbleView, layoutParams)

                            val isOverTrash = isOverDeleteZone()
                            deleteZoneView.alpha = if (isOverTrash) 1.0f else 0.5f
                        }
                        return true
                    }

                    MotionEvent.ACTION_UP -> {
                        deleteZoneImage.visibility = View.GONE
                        deleteZoneView.visibility = View.GONE
                        deleteZoneView.alpha = 0.5f

                        return if (isDragging) {
                            if (isOverDeleteZone()) {
                                sendBroadcast(Intent(ACTION_BUBBLE_STATE).putExtra(EXTRA_RUNNING, false).setPackage(packageName))
                                stopSelf()
                            } else {
                                val half = Resources.getSystem().displayMetrics.widthPixels / 2
                                layoutParams.x = if (layoutParams.x < half) 0 else Resources.getSystem().displayMetrics.widthPixels
                                windowManager.updateViewLayout(bubbleView, layoutParams)
                            }
                            true
                        } else {
                            if (OverlayAgent.taskActive) {
                                Toast.makeText(this@BubbleService, "請按叉叉先結束此次任務，再發問喔！", Toast.LENGTH_SHORT).show()
                                return true
                            }
                            // 點擊事件 → 開啟對話框 Activity
                            val intent = Intent(this@BubbleService, ChatDialogActivity::class.java).apply {
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)               // 必要：從 Service 啟動
                                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)             // 清除任何現有任務（避免主畫面跳出）
                                addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION)           // 不要動畫（更像 Dialog）
                                addFlags(Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS)   // 不加入最近任務
                                addFlags(Intent.FLAG_ACTIVITY_NO_HISTORY)             // 關掉後不保留
                            }
                            startActivity(intent)
                            true
                        }
                    }
                }
                return false
            }
        })
    }

    private fun isOverDeleteZone(): Boolean {
        val bubblePos = IntArray(2)
        val trashPos = IntArray(2)
        bubbleView.getLocationOnScreen(bubblePos)
        deleteZoneView.getLocationOnScreen(trashPos)

        val bubbleRect = Rect(
            bubblePos[0],
            bubblePos[1],
            bubblePos[0] + bubbleView.width,
            bubblePos[1] + bubbleView.height
        )
        val trashRect = Rect(
            trashPos[0],
            trashPos[1],
            trashPos[0] + deleteZoneView.width,
            trashPos[1] + deleteZoneView.height
        )

        return Rect.intersects(bubbleRect, trashRect)
    }

    private fun dpToPx(dp: Int): Int {
        return (dp * Resources.getSystem().displayMetrics.density).toInt()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (::bubbleView.isInitialized) {
            windowManager.removeView(bubbleView)
        }
        if (::deleteZoneView.isInitialized) {
            windowManager.removeView(deleteZoneView)
        }
        sendBroadcast(Intent(ACTION_BUBBLE_STATE).putExtra(EXTRA_RUNNING, false).setPackage(packageName))
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
