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
        "https://shkar-bourse-pro2.onrender.com/six-month-opportunities"

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
            text("📊 وضعیت بازار", 20f)
        )

        val marketCard = text(
            "در حال دریافت اطلاعات بازار...",
            16f
        )

        marketCard.setBackgroundColor(Color.rgb(24, 36, 52))

        content.addView(
            marketCard,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 10, 0, 25)
            }
        )

        content.addView(
            text("🚀 فرصت‌های سرمایه‌گذاری ۶ ماهه", 20f)
        )

        val opportunitiesContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }

        content.addView(
            opportunitiesContainer,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 10, 0, 25)
            }
        )

        content.addView(
            text("⚠️ توجه", 20f)
        )

        val warning = text(
            "درصد رشد نمایش‌داده‌شده برآورد تحلیلی سیستم است و " +
            "به هیچ عنوان سود تضمینی محسوب نمی‌شود.",
            15f,
            Color.LTGRAY
        )

        warning.setBackgroundColor(Color.rgb(24, 36, 52))
        content.addView(warning)

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
            marketCard,
            opportunitiesContainer
        )
    }

    private fun loadOpportunities(
        marketCard: TextView,
        container: LinearLayout
    ) {

        thread {

            try {

                val url = URL(apiUrl)

                val connection =
                    url.openConnection() as HttpURLConnection

                connection.requestMethod = "GET"
                connection.connectTimeout = 15000
                connection.readTimeout = 15000

                val responseCode = connection.responseCode

                if (responseCode != 200) {

                    runOnUiThread {

                        marketCard.text =
                            "خطا در دریافت اطلاعات\nHTTP: $responseCode"

                    }

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

                    container.removeAllViews()

                    for (i in 0 until opportunities.length()) {

                        val item =
                            opportunities.getJSONObject(i)

                        addOpportunityCard(
                            container,
                            item
                        )
                    }

                    marketCard.text =
                        "اطلاعات فرصت‌های ۶ ماهه با موفقیت دریافت شد.\n\n" +
                        "تعداد فرصت‌ها: ${opportunities.length()}"

                }

            } catch (e: Exception) {

                runOnUiThread {

                    marketCard.text =
                        "خطا در اتصال به سرور:\n${e.message}"

                    container.removeAllViews()

                    container.addView(
                        text(
                            "اطلاعاتی دریافت نشد.\nلطفاً اتصال اینترنت را بررسی کنید.",
                            16f
                        )
                    )
                }
            }
        }
    }

    private fun addOpportunityCard(
        container: LinearLayout,
        item: JSONObject
    ) {

        val rank =
            item.optInt("rank", 0)

        val ticker =
            item.optString("ticker", "---")

        val name =
            item.optString("name", "---")

        val sector =
            item.optString("sector", "---")

        val currentPrice =
            item.optLong("current_price", 0)

        val targetPrice =
            item.optLong("target_price_6m", 0)

        val growth =
            item.optInt("estimated_growth_percent", 0)

        val risk =
            item.optString("risk", "---")

        val reasons =
            item.optJSONArray("reasons")

        val reasonsText =
            StringBuilder()

        if (reasons != null) {

            for (i in 0 until reasons.length()) {

                reasonsText.append(
                    "• ${reasons.getString(i)}\n"
                )
            }
        }

        val card = LinearLayout(this).apply {

            orientation = LinearLayout.VERTICAL

            setPadding(20, 20, 20, 20)

            setBackgroundColor(
                Color.rgb(24, 36, 52)
            )
        }

        val title = text(
            "🏆 رتبه $rank — $ticker",
            20f
        )

        title.setTextColor(
            Color.rgb(255, 215, 80)
        )

        card.addView(title)

        card.addView(
            text(
                name,
                17f
            )
        )

        card.addView(
            text(
                "صنعت: $sector",
                14f,
                Color.LTGRAY
            )
        )

        card.addView(
            text(
                "💰 قیمت فعلی: ${formatNumber(currentPrice)}",
                16f
            )
        )

        card.addView(
            text(
                "🎯 هدف ۶ ماهه: ${formatNumber(targetPrice)}",
                16f
            )
        )

        val growthText = text(
            "📈 سود احتمالی ۶ ماهه: +$growth٪",
            19f
        )

        growthText.setTextColor(
            Color.rgb(80, 220, 120)
        )

        card.addView(growthText)

        card.addView(
            text(
                "⚠️ ریسک: $risk",
                15f,
                Color.LTGRAY
            )
        )

        if (reasonsText.isNotEmpty()) {

            card.addView(
                text(
                    "🔎 دلایل انتخاب:\n${reasonsText}",
                    14f,
                    Color.LTGRAY
                )
            )
        }

        container.addView(
            card,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 0, 0, 16)
            }
        )
    }

    private fun formatNumber(
        number: Long
    ): String {

        return String.format(
            "%,d",
            number
        )
    }
}
```
