package com.example.bubbleassistant

import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Extremely small single-port HTTP server to expose latest screen info JSON.
 * - GET /health -> 200 OK, plain text
 * - GET /screen-info -> 200 OK, application/json
 *
 * Designed to be used over ADB port forwarding or on the same LAN.
 */
class ScreenInfoServer(
    private val jsonProvider: () -> String,
    private val port: Int = DEFAULT_PORT
) {
    // Secondary constructor to support (port, jsonProvider) ordering
    constructor(port: Int, jsonProvider: () -> String) : this(jsonProvider, port)

    private val running = AtomicBoolean(false)
    private var serverThread: Thread? = null
    private val clientPool = Executors.newCachedThreadPool()

    fun start() {
        if (running.getAndSet(true)) return
        serverThread = Thread({ runServer() }, "ScreenInfoServer").apply { start() }
    }

    fun stop() {
        running.set(false)
        try {
            // Trigger ServerSocket.accept() to unblock by connecting to self
            Socket("127.0.0.1", port).close()
        } catch (_: Throwable) {
        }
        try {
            serverThread?.join(1000)
        } catch (_: Throwable) {
        } finally {
            serverThread = null
        }
        clientPool.shutdownNow()
    }

    private fun runServer() {
        var serverSocket: ServerSocket? = null
        try {
            serverSocket = ServerSocket(port)
            while (running.get()) {
                val client = try { serverSocket.accept() } catch (_: Throwable) { null } ?: continue
                clientPool.execute { handleClient(client) }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "Server error", t)
        } finally {
            try { serverSocket?.close() } catch (_: Throwable) {}
        }
    }

    private fun handleClient(socket: Socket) {
        socket.use { s ->
            val reader = BufferedReader(InputStreamReader(s.getInputStream()))
            val writer = PrintWriter(s.getOutputStream())

            // Read the request line
            val requestLine = reader.readLine() ?: return
            val parts = requestLine.split(" ")
            val method = parts.getOrNull(0) ?: ""
            val path = parts.getOrNull(1) ?: "/"
            
            Log.i(TAG, "HTTP 請求: $method $path")

            // Drain headers
            while (true) {
                val line = reader.readLine() ?: break
                if (line.isEmpty()) break
            }

            if (method != "GET") {
                respond(writer, 405, "Method Not Allowed", "text/plain", "Only GET supported")
                return
            }

            when (path) {
                "/health" -> {
                    Log.i(TAG, "健康檢查請求")
                    respond(writer, 200, "OK", "text/plain", "ok")
                }
                "/screen-info" -> {
                    Log.i(TAG, "螢幕資訊請求")
                    val json = jsonProvider.invoke()
                    Log.i(TAG, "回應螢幕資訊長度: ${json.length} 字元")
                    respond(writer, 200, "OK", "application/json; charset=utf-8", json)
                }
                else -> {
                    Log.w(TAG, "未知路徑: $path")
                    respond(writer, 404, "Not Found", "text/plain", "not found")
                }
            }
        }
    }

    private fun respond(
        writer: PrintWriter,
        status: Int,
        message: String,
        contentType: String,
        body: String
    ) {
        val bytes = body.toByteArray(Charsets.UTF_8)
        writer.apply {
            println("HTTP/1.1 $status $message")
            println("Content-Type: $contentType")
            println("Content-Length: ${bytes.size}")
            println("Connection: close")
            println()
            flush()
        }
        // Write body bytes using socket's raw stream to avoid charset issues
        try {
            writer.flush()
            writer.checkError()
            // We already wrote headers, now write body via underlying stream
        } catch (_: Throwable) {}
        try {
            writer.append(body)
            writer.flush()
        } catch (_: Throwable) {}
    }

    companion object {
        const val DEFAULT_PORT: Int = 8765
        private const val TAG: String = "ScreenInfoServer"
    }
}
