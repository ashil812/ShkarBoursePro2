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

    private fun text(
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
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(10, 18, 30))
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 30, 20, 20)
        }

        header.addView(
            text("Shkar Bourse", 28f)
        )

        header.addView(
            text(
                "تحلیل هوشمند بورس ایران",
                15f,
                Color.LTGRAY
            )
        )

        root.addView(header)

        val scroll = ScrollView(this)

        content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 10, 20, 30)
        }

        content.addView(
            text(
                "🔥 فرصت‌های سرمایه‌گذاری ۶ ماهه",
                20f
            )
        )

        content.addView(
            text(
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

                val responseCode = connection.responseCode

                if (responseCode != 200) {
                    showError("خطا در دریافت اطلاعات: HTTP $responseCode")
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
                        text(
                            "🔥 فرصت‌های سرمایه‌گذاری ۶ ماهه",
                            20f
                        )
                    )

                    content.addView(
                        text(
                            "تعداد فرصت‌ها: ${opportunities.length()}",
                            15f,
                            Color.LTGRAY
                        )
                    )

                    content.addView(
                        text(
                            json.optString(
                                "warning",
                                "درصد رشد، برآورد تحلیلی است و سود تضمینی نیست."
                            ),
                            13f,
                            Color.YELLOW
                        )
                    )

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
                            item.optLong("current_price", 0)

                        val targetPrice =
                            item.optLong("target_price_6m", 0)

                        val growth =
                            item.optDouble(
                                "estimated_growth_percent",
                                0.0
                            )

                        val risk =
                            item.optString("risk", "-")

                        val change =
                            item.optDouble(
                                "change_percent",
                                0.0
                            )

                        val score =
                            item.optInt("rank_score", 0)

                        val tradeValue =
                            item.optLong(
                                "trade_value",
                                0
                            )

                        val peText =
                            if (item.isNull("pe")) {
                                "-"
                            } else {
                                item.optString("pe", "-")
                            }

                        val reasons =
                            item.optJSONArray("reasons")

                        val reasonsText =
                            buildString {

                                if (reasons != null) {

                                    for (j in 0 until reasons.length()) {

                                        append("• ")
                                        append(reasons.optString(j))

                                        if (j < reasons.length() - 1) {
                                            append("\n")
                                        }
                                    }
                                }
                            }

                        val card =
                            LinearLayout(this@MainActivity).apply {

                                orientation =
                                    LinearLayout.VERTICAL

                                setPadding(
                                    20,
                                    20,
                                    20,
                                    20
                                )

                                setBackgroundColor(
                                    Color.rgb(24, 36, 52)
                                )
                            }

                        card.addView(
                            text(
                                "رتبه $rank | $ticker",
                                21f
                            )
                        )

                        card.addView(
                            text(name, 18f)
                        )

                        card.addView(
                            text(
                                "امتیاز: $score",
                                15f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            text(
                                "بخش: $sector",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            text(
                                "قیمت فعلی: $currentPrice",
                                15f
                            )
                        )

                        card.addView(
                            text(
                                "هدف ۶ ماهه: $targetPrice",
                                15f
                            )
                        )

                        card.addView(
                            text(
                                "رشد برآوردی: $growth٪",
                                18f
                            )
                        )

                        card.addView(
                            text(
                                "تغییر امروز: $change٪",
                                15f
                            )
                        )

                        card.addView(
                            text(
                                "ریسک: $risk",
                                15f
                            )
                        )

                        card.addView(
                            text(
                                "P/E: $peText",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            text(
                                "ارزش معاملات: $tradeValue",
                                14f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            text(
                                "دلایل:\n$reasonsText",
                                14f,
                                Color.LTGRAY
                            )
                        )

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
                    "خطا در اتصال به سرور:\n${e.message}"
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
                text(
                    "❌ خطا",
                    22f
                )
            )

            content.addView(
                text(
                    message,
                    16f,
                    Color.LTGRAY
                )
            )
        }
    }
}
```
