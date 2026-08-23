```kotlin
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
        "https://shkar-bourse-pro2.onrender.com"

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
            text("تحلیل هوشمند بورس ایران", 15f, Color.LTGRAY)
        )

        root.addView(header)

        val scroll = ScrollView(this)

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 10, 20, 30)
        }

        content.addView(
            text("🔥 فرصت‌های سرمایه‌گذاری ۶ ماهه", 20f)
        )

        val status = text(
            "در حال دریافت اطلاعات از سرور...",
            16f
        )

        status.setBackgroundColor(Color.rgb(24, 36, 52))

        content.addView(
            status,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 10, 0, 20)
            }
        )

        val opportunitiesContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }

        content.addView(opportunitiesContainer)

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

        loadOpportunities(
            status,
            opportunitiesContainer
        )
    }

    private fun loadOpportunities(
        status: TextView,
        container: LinearLayout
    ) {

        thread {

            try {

                val url = URL(
                    "$apiUrl/six-month-opportunities"
                )

                val connection =
                    url.openConnection() as HttpURLConnection

                connection.requestMethod = "GET"
                connection.connectTimeout = 15000
                connection.readTimeout = 15000

                val responseCode =
                    connection.responseCode

                if (responseCode != 200) {
                    throw Exception(
                        "HTTP $responseCode"
                    )
                }

                val response =
                    connection.inputStream
                        .bufferedReader()
                        .use { it.readText() }

                val json =
                    JSONObject(response)

                val opportunities =
                    json.getJSONArray("opportunities")

                runOnUiThread {

                    status.text =
                        "✅ اطلاعات با موفقیت دریافت شد\n" +
                        "تعداد فرصت‌ها: ${opportunities.length()}"

                    container.removeAllViews()

                    for (i in 0 until opportunities.length()) {

                        val item =
                            opportunities.getJSONObject(i)

                        val rank =
                            item.optInt("rank")

                        val ticker =
                            item.optString("ticker")

                        val name =
                            item.optString("name")

                        val sector =
                            item.optString("sector")

                        val currentPrice =
                            item.optDouble(
                                "current_price"
                            )

                        val targetPrice =
                            item.optDouble(
                                "target_price_6m"
                            )

                        val growth =
                            item.optDouble(
                                "estimated_growth_percent"
                            )

                        val risk =
                            item.optString("risk")

                        val score =
                            item.optInt("rank_score")

                        val change =
                            item.optDouble(
                                "change_percent"
                            )

                        val reasons =
                            item.optJSONArray(
                                "reasons"
                            )

                        val reasonText =
                            StringBuilder()

                        if (reasons != null) {
                            for (j in 0 until reasons.length()) {
                                reasonText.append(
                                    "• ${reasons.getString(j)}\n"
                                )
                            }
                        }

                        val card =
                            LinearLayout(this).apply {
                                orientation =
                                    LinearLayout.VERTICAL

                                setPadding(
                                    20,
                                    18,
                                    20,
                                    18
                                )

                                setBackgroundColor(
                                    Color.rgb(
                                        24,
                                        36,
                                        52
                                    )
                                )
                            }

                        card.addView(
                            text(
                                "رتبه $rank  |  $ticker",
                                21f
                            )
                        )

                        card.addView(
                            text(
                                name,
                                18f,
                                Color.LTGRAY
                            )
                        )

                        card.addView(
                            text(
                                "امتیاز: $score",
                                16f
                            )
                        )

                        card.addView(
                            text(
                                "قیمت فعلی: ${formatNumber(currentPrice)}",
                                16f
                            )
                        )

                        card.addView(
                            text(
                                "هدف ۶ ماهه: ${formatNumber(targetPrice)}",
                                16f
                            )
                        )

                        card.addView(
                            text(
                                "رشد برآوردی: ${formatNumber(growth)}٪",
                                17f
                            )
                        )

                        card.addView(
                            text(
                                "تغییر روزانه: ${formatNumber(change)}٪",
                                16f
                            )
                        )

                        card.addView(
                            text(
                                "ریسک: $risk",
                                16f
                            )
                        )

                        card.addView(
                            text(
                                "دلیل انتخاب:\n$reasonText",
                                15f,
                                Color.LTGRAY
                            )
                        )

                        container.addView(
                            card,
                            LinearLayout.LayoutParams(
                                LinearLayout.LayoutParams.MATCH_PARENT,
                                LinearLayout.LayoutParams.WRAP_CONTENT
                            ).apply {
                                setMargins(
                                    0,
                                    0,
                                    0,
                                    18
                                }
                            }
                        )
                    }
                }

                connection.disconnect()

            } catch (e: Exception) {

                runOnUiThread {

                    status.text =
                        "❌ خطا در دریافت اطلاعات\n\n" +
                        e.message

                }
            }
        }
    }

    private fun formatNumber(
        number: Double
    ): String {

        return if (number % 1.0 == 0.0) {
            number.toLong().toString()
        } else {
            String.format(
                "%.2f",
                number
            )
        }
    }
}
```
