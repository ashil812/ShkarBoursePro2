package com.ashil812.shkarboursepro

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {

    private val apiUrl =
        "https://shkar-bourse-pro2.onrender.com/six-month-opportunities"

    private lateinit var content: LinearLayout

    private fun makeText(
        value: String,
        size: Float,
        color: Int = Color.WHITE
    ): TextView {
        return TextView(this).apply {
            text = value
            textSize = size
            setTextColor(color)
            setPadding(24, 16, 24, 16)
            gravity = Gravity.RIGHT
            textDirection = TextView.TEXT_DIRECTION_RTL
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(10, 18, 30))
            layoutDirection = LinearLayout.LAYOUT_DIRECTION_RTL
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 30, 20, 20)
            layoutDirection = LinearLayout.LAYOUT_DIRECTION_RTL
        }

        header.addView(
            makeText(
                "Shkar Bourse",
                28f
            )
        )

        header.addView(
            makeText(
                "تحلیل هوشمند بورس ایران",
                15f,
                Color.LTGRAY
            )
        )

        root.addView(header)

        val scroll = ScrollView(this).apply {
            layoutDirection = ScrollView.LAYOUT_DIRECTION_RTL
        }

        content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 10, 20, 30)
            layoutDirection = LinearLayout.LAYOUT_DIRECTION_RTL
        }

        content.addView(
            makeText(
                "🔥 فرصت‌های سرمایه‌گذاری ۶ ماهه",
                20f
            )
        )

        content.addView(
            makeText(
                "در حال دریافت اطلاعات از سرور...",
                16f
            )
        )

        scroll.addView(content)

        root.addView(
            scroll,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        setContentView(root)

        loadOpportunities()
    }

    private fun loadOpportunities() {

        thread {

            var connection: HttpURLConnection? = null

            try {

                val url = URL(apiUrl)

                connection = url.openConnection() as HttpURLConnection

                connection.requestMethod = "GET"
                connection.connectTimeout = 15000
                connection.readTimeout = 15000
                connection.setRequestProperty(
                    "Accept",
                    "application/json"
                )

                val responseCode = connection.responseCode

                if (responseCode != 200) {
                    showError(
                        "خطا در دریافت اطلاعات: HTTP $responseCode"
                    )
                    return@thread
                }

                val response =
                    connection.inputStream
                        .bufferedReader()
                        .use { it.readText() }

                val json = JSONObject(response)

                val opportunities =
                    json.getJSONArray("opportunities")

                runOnUiThread {

                    content.removeAllViews()

                    content.addView(
                        makeText(
                            "🔥 فرصت‌های سرمایه‌گذاری ۶ ماهه",
                            20f
                        )
                    )

                    val title =
                        json.optString(
                            "title",
                            "فرصت‌های سرمایه‌گذاری ۶ ماهه"
                        )

                    content.addView(
                        makeText(
                            title,
                            16f,
                            Color.LTGRAY
                        )
                    )

                    content.addView(
                        makeText(
                            "تعداد فرصت‌ها: ${opportunities.length()}",
                            15f,
                            Color.LTGRAY
                        )
                    )

                    val warning =
                        json.optString("warning", "")

                    if (warning.isNotEmpty()) {
                        content.addView(
                            makeText(
                                "⚠️ $warning",
                                14f,
                                Color.YELLOW
                            )
                        )
                    }

                    for (i in 0 until opportunities.length()) {

                        val item =
                            opportunities.getJSONObject(i)

                        val rank =
                            item.optInt("rank", i + 1)

                        val ticker =
                            item.optString("ticker", "-")

                        val name =
                            item.optString("name", "-")

                        val sector =
                            item.optString("sector", "-")

                        val currentPrice =
                            item.optLong(
                                "current_price",
                                0
                            )

                        val targetPrice =
                            item.optLong(
                                "target_price_6m",
                                0
                            )

                        val growth =
                            item.optDouble(
                                "estimated_growth_percent",
                                0.0
                            )

                        val risk =
                            item.optString(
                                "risk",
                                "-"
                            )

                        val change =
                            item.optDouble(
                                "change_percent",
                                0.0
                            )

                        val score =
                            item.optInt(
                                "rank_score",
                                0
                            )

                        val tradeValue =
                            item.optLong(
                                "trade_value",
                                0
                            )

                        val peText =
                            if (
                                item.isNull("pe")
                            ) {
                                "-"
                            } else {
                                item.optDouble(
                                    "pe",
                                    0.0
                                ).toString()
                            }

                        val reasons =
                            item.optJSONArray("reasons")

                        val reasonsText =
                            buildString {

                                if (reasons != null) {

                                    for (
                                        j in 0 until reasons.length()
                                    ) {

                                        append("• ")
                                        append(
                                            reasons.optString(j)
                                        )

                                        if (
                                            j <
                                            reasons.length() - 1
                                        ) {
                                            append("\n")
                                        }
                                    }
                                }
                            }

                        val card =
                            LinearLayout(
                                this@MainActivity
                            ).apply {

                                orientation =
                                    LinearLayout.VERTICAL

                                setPadding(
                                    20,
                                    20,
                                    20,
                                    20
                                )

                                setBackgroundColor(
                                    Color.rgb(
                                        24,
                                        36,
                                        52
                                    )

                                layoutDirection =
                                    LinearLayout
                                        .LAYOUT_DIRECTION_RTL
                            }

                        card.addView(
                            makeText(
                                "رتبه $rank  |  $ticker",
                                21f
                            )
                        )

                        card.addView(
                            makeText(
                                name,
                                18f
                            )
                        )

                        card.addView(
                            makeText(
                                "امتیاز: $score",
                                15f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            makeText(
                                "بخش: $sector",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            makeText(
                                "قیمت فعلی: $currentPrice",
                                15f
                            )
                        )

                        card.addView(
                            makeText(
                                "هدف ۶ ماهه: $targetPrice",
                                15f
                            )
                        )

                        card.addView(
                            makeText(
                                "رشد برآوردی: $growth٪",
                                18f
                            )
                        )

                        card.addView(
                            makeText(
                                "تغییر امروز: $change٪",
                                15f
                            )
                        )

                        card.addView(
                            makeText(
                                "ریسک: $risk",
                                15f
                            )
                        )

                        card.addView(
                            makeText(
                                "ارزش معاملات: $tradeValue",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            makeText(
                                "P/E: $peText",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        if (reasonsText.isNotEmpty()) {
                            card.addView(
                                makeText(
                                    "دلایل:\n$reasonsText",
                                    14f,
                                    Color.LTGRAY
                                )
                            )
                        }

                        content.addView(
                            card,
                            LinearLayout.LayoutParams(
                                LinearLayout.LayoutParams.MATCH_PARENT,
                                LinearLayout.LayoutParams.WRAP_CONTENT
                            ).apply {
                                setMargins(
                                    0,
                                    10,
                                    0,
                                    15
                                )
                            }
                        )
                    }
                }

            } catch (e: Exception) {

                showError(
                    "خطا در اتصال به سرور:\n${e.message ?: "خطای نامشخص"}"
                )

            } finally {

                connection?.disconnect()
            }
        }
    }

    private fun showError(message: String) {

        runOnUiThread {

            content.removeAllViews()

            content.addView(
                makeText(
                    "❌ خطا",
                    22f
                )
            )

            content.addView(
                makeText(
                    message,
                    16f,
                    Color.LTGRAY
                )
            )
        }
    }
}
