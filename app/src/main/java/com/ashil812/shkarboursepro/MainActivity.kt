package com.ashil812.shkarboursepro

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {

    private val apiUrl =
        "https://shkar-bourse-pro2.onrender.com/opportunities"

    private fun makeText(
        value: String,
        size: Float,
        color: Int = Color.WHITE
    ): TextView {

        return TextView(this).apply {
            text = value
            textSize = size
            setTextColor(color)
            setPadding(24, 18, 24, 18)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(
                Color.rgb(10, 18, 30)
            )
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 30, 20, 20)
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

        val scrollView = ScrollView(this)

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 10, 20, 30)
        }

        val connectionStatus = makeText(
            "🔄 در حال اتصال به سرور...",
            16f,
            Color.YELLOW
        )

        content.addView(connectionStatus)

        content.addView(
            makeText(
                "🔥 بهترین فرصت‌های ۶ ماهه",
                21f
            )
        )

        val opportunitiesContainer =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
            }

        content.addView(
            opportunitiesContainer
        )

        scrollView.addView(content)

        root.addView(
            scrollView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        setContentView(root)

        loadOpportunities(
            connectionStatus,
            opportunitiesContainer
        )
    }

    private fun loadOpportunities(
        statusText: TextView,
        container: LinearLayout
    ) {

        thread {

            var connection:
                    HttpURLConnection? = null

            try {

                val url = URL(apiUrl)

                connection =
                    url.openConnection()
                            as HttpURLConnection

                connection.requestMethod = "GET"

                connection.connectTimeout =
                    15000

                connection.readTimeout =
                    15000

                connection.setRequestProperty(
                    "Accept",
                    "application/json"
                )

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
                        .use {
                            it.readText()
                        }

                val json =
                    JSONObject(response)

                val opportunities =
                    json.getJSONArray(
                        "opportunities"
                    )

                runOnUiThread {

                    statusText.text =
                        "✅ اتصال به سرور برقرار است"

                    statusText.setTextColor(
                        Color.GREEN
                    )

                    container.removeAllViews()

                    for (
                        i in 0 until
                        opportunities.length()
                    ) {

                        val item =
                            opportunities
                                .getJSONObject(i)

                        val rank =
                            item.getInt("rank")

                        val ticker =
                            item.getString(
                                "ticker"
                            )

                        val name =
                            item.getString(
                                "name"
                            )

                        val price =
                            item.getLong(
                                "current_price"
                            )

                        val target =
                            item.getLong(
                                "target_price_6m"
                            )

                        val growth =
                            item.getDouble(
                                "estimated_growth_percent"
                            )

                        val risk =
                            item.getString(
                                "risk"
                            )

                        val score =
                            item.getInt(
                                "rank_score"
                            )

                        val reasons =
                            item.getJSONArray(
                                "reasons"
                            )

                        val reasonBuilder =
                            StringBuilder()

                        for (
                            j in 0 until
                            reasons.length()
                        ) {

                            reasonBuilder
                                .append("• ")
                                .append(
                                    reasons.getString(j)
                                )
                                .append("\n")
                        }

                        val cardText =
                            """
                            🏆 رتبه $rank
                            
                            $ticker
                            $name
                            
                            💰 قیمت فعلی: $price
                            🎯 هدف ۶ ماهه: $target
                            
                            📈 رشد برآوردی: $growth٪
                            ⭐ امتیاز: $score
                            ⚠️ ریسک: $risk
                            
                            دلایل:
                            $reasonBuilder
                            """.trimIndent()

                        val card =
                            makeText(
                                cardText,
                                16f
                            )

                        card.setBackgroundColor(
                            Color.rgb(
                                24,
                                36,
                                52
                            )
                        )

                        val params =
                            LinearLayout.LayoutParams(
                                LinearLayout.LayoutParams.MATCH_PARENT,
                                LinearLayout.LayoutParams.WRAP_CONTENT
                            )

                        params.setMargins(
                            0,
                            10,
                            0,
                            15
                        )

                        container.addView(
                            card,
                            params
                        )
                    }
                }

            } catch (e: Exception) {

                runOnUiThread {

                    statusText.text =
                        "❌ خطا در اتصال به سرور\n\n" +
                        e.message

                    statusText.setTextColor(
                        Color.RED
                    )
                }

            } finally {

                connection?.disconnect()
            }
        }
    }
}
