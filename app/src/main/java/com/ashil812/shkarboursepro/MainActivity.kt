package com.ashil812.shkarboursepro

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {

    // =========================================================
    // API
    // =========================================================

    private val baseApiUrl =
        "https://shkar-bourse-pro2.onrender.com"

    private val healthUrl =
        "$baseApiUrl/health"

    private val shortTermUrl =
        "$baseApiUrl/short-term-opportunities"

    private val sixMonthUrl =
        "$baseApiUrl/six-month-opportunities"


    // =========================================================
    // UI
    // =========================================================

    private lateinit var content: LinearLayout
    private lateinit var refreshButton: Button


    // =========================================================
    // COLORS
    // =========================================================

    private val backgroundColor =
        Color.rgb(10, 18, 30)

    private val cardColor =
        Color.rgb(24, 36, 52)

    private val secondaryColor =
        Color.LTGRAY

    private val whiteColor =
        Color.WHITE


    // =========================================================
    // TEXT
    // =========================================================

    private fun makeText(
        value: String,
        size: Float,
        color: Int = whiteColor
    ): TextView {

        return TextView(this).apply {

            text = value

            textSize = size

            setTextColor(color)

            gravity =
                Gravity.RIGHT

            setPadding(
                20,
                12,
                20,
                12
            )
        }
    }


    // =========================================================
    // CARD
    // =========================================================

    private fun makeCard(): LinearLayout {

        return LinearLayout(
            this
        ).apply {

            orientation =
                LinearLayout.VERTICAL

            setPadding(
                20,
                18,
                20,
                18
            )

            setBackgroundColor(
                cardColor
            )
        }
    }


    // =========================================================
    // ON CREATE
    // =========================================================

    override fun onCreate(
        savedInstanceState: Bundle?
    ) {

        super.onCreate(
            savedInstanceState
        )

        buildMainScreen()

        loadAllData()
    }


    // =========================================================
    // BUILD MAIN SCREEN
    // =========================================================

    private fun buildMainScreen() {

        val root =
            LinearLayout(this).apply {

                orientation =
                    LinearLayout.VERTICAL

                setBackgroundColor(
                    backgroundColor
                )
            }


        // ---------------------------------------------------------
        // HEADER
        // ---------------------------------------------------------

        val header =
            LinearLayout(this).apply {

                orientation =
                    LinearLayout.VERTICAL

                setPadding(
                    20,
                    30,
                    20,
                    15
                )

                setBackgroundColor(
                    backgroundColor
                )
            }


        header.addView(
            makeText(
                "Shkar Bourse",
                29f
            )
        )


        header.addView(
            makeText(
                "تحلیل هوشمند بورس ایران",
                15f,
                secondaryColor
            )
        )


        root.addView(
            header
        )


        // ---------------------------------------------------------
        // REFRESH BUTTON
        // ---------------------------------------------------------

        refreshButton =
            Button(this).apply {

                text =
                    "🔄 بروزرسانی اطلاعات"

                textSize = 15f

                setOnClickListener {

                    loadAllData()
                }
            }


        val refreshParams =
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )

        refreshParams.setMargins(
            20,
            5,
            20,
            10
        )


        root.addView(
            refreshButton,
            refreshParams
        )


        // ---------------------------------------------------------
        // SCROLL
        // ---------------------------------------------------------

        val scrollView =
            ScrollView(this)


        content =
            LinearLayout(this).apply {

                orientation =
                    LinearLayout.VERTICAL

                setPadding(
                    20,
                    10,
                    20,
                    30
                )
            }


        scrollView.addView(
            content
        )


        root.addView(
            scrollView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )


        setContentView(
            root
        )


        showLoading()
    }


    // =========================================================
    // LOADING
    // =========================================================

    private fun showLoading() {

        content.removeAllViews()


        content.addView(
            makeText(
                "⏳ در حال اتصال به سرور...",
                19f
            )
        )


        content.addView(
            makeText(
                "در حال دریافت وضعیت بازار و تحلیل نمادها...",
                14f,
                secondaryColor
            )
        )
    }


    // =========================================================
    // LOAD ALL
    // =========================================================

    private fun loadAllData() {

        refreshButton.isEnabled =
            false

        refreshButton.text =
            "⏳ در حال بروزرسانی..."


        showLoading()


        thread {

            try {

                val health =
                    requestJson(
                        healthUrl
                    )


                val shortTerm =
                    requestJson(
                        shortTermUrl
                    )


                val sixMonth =
                    requestJson(
                        sixMonthUrl
                    )


                runOnUiThread {

                    refreshButton.isEnabled =
                        true

                    refreshButton.text =
                        "🔄 بروزرسانی اطلاعات"


                    content.removeAllViews()


                    showHealth(
                        health
                    )


                    addSeparator()


                    showShortTerm(
                        shortTerm
                    )


                    addSeparator()


                    showSixMonth(
                        sixMonth
                    )
                }

            } catch (e: Exception) {

                showError(
                    "خطا در اتصال به سرور:\n${e.message ?: "خطای نامشخص"}"
                )
            }
        }
    }


    // =========================================================
    // HTTP REQUEST
    // =========================================================

    private fun requestJson(
        apiUrl: String
    ): JSONObject {

        var connection:
            HttpURLConnection? = null


        try {

            val url =
                URL(apiUrl)


            connection =
                url.openConnection()
                    as HttpURLConnection


            connection.requestMethod =
                "GET"


            connection.connectTimeout =
                15000


            connection.readTimeout =
                20000


            connection.setRequestProperty(
                "Accept",
                "application/json"
            )


            val responseCode =
                connection.responseCode


            val stream =

                if (
                    responseCode in 200..299
                ) {

                    connection.inputStream

                } else {

                    connection.errorStream
                }


            val response =
                stream
                    ?.bufferedReader()
                    ?.use {
                        it.readText()
                    }
                    ?: ""


            if (
                responseCode !in 200..299
            ) {

                throw Exception(
                    "HTTP $responseCode\n$response"
                )
            }


            return JSONObject(
                response
            )

        } finally {

            connection?.disconnect()
        }
    }


    // =========================================================
    // HEALTH
    // =========================================================

    private fun showHealth(
        json: JSONObject
    ) {

        val card =
            makeCard()


        card.addView(
            makeText(
                "📊 وضعیت بازار",
                21f
            )
        )


        val marketOpen =
            json.optBoolean(
                "market_open",
                false
            )


        val marketMode =
            json.optString(
                "market_mode",
                "inactive"
            )


        val marketText =

            if (marketOpen) {

                "🟢 بازار باز است"

            } else {

                "🔴 بازار بسته است"
            }


        card.addView(
            makeText(
                marketText,
                17f
            )
        )


        card.addView(
            makeText(
                "وضعیت جمع‌آوری: $marketMode",
                14f,
                secondaryColor
            )
        )


        val totalSymbols =
            json.opt(
                "total_symbols"
            )


        if (
            totalSymbols != null
            && totalSymbols != JSONObject.NULL
        ) {

            card.addView(
                makeText(
                    "تعداد نمادها: $totalSymbols",
                    15f
                )
            )
        }


        val cachedStocks =
            json.optInt(
                "cached_stocks",
                0
            )


        card.addView(
            makeText(
                "نمادهای دریافت‌شده: $cachedStocks",
                15f
            )
        )


        val cycles =
            json.optInt(
                "market_cycles_completed",
                0
            )


        card.addView(
            makeText(
                "چرخه‌های کامل‌شده: $cycles",
                15f
            )
        )


        val dailyUsed =
            json.optInt(
                "daily_requests_used",
                0
            )


        val dailyRemaining =
            json.optInt(
                "daily_requests_remaining",
                100
            )


        card.addView(
            makeText(
                "درخواست‌های امروز: $dailyUsed / 100",
                15f
            )
        )


        card.addView(
            makeText(
                "درخواست‌های باقی‌مانده: $dailyRemaining",
                15f,
                secondaryColor
            )
        )


        val nextRequest =
            json.optInt(
                "seconds_until_next_request",
                0
            )


        if (
            nextRequest > 0
        ) {

            card.addView(
                makeText(
                    "درخواست بعدی: $nextRequest ثانیه دیگر",
                    14f,
                    secondaryColor
                )
            )
        }


        val historyStarted =
            json.optBoolean(
                "history_started",
                false
            )


        val historyComplete =
            json.optBoolean(
                "history_complete",
                false
            )


        if (
            historyStarted
        ) {

            val historyText =

                if (historyComplete) {

                    "📚 تاریخچه نمادهای برتر کامل شده است."

                } else {

                    "📚 دریافت تاریخچه نمادهای برتر در حال انجام است."
                }


            card.addView(
                makeText(
                    historyText,
                    14f,
                    secondaryColor
                )
            )
        }


        addCard(
            card
        )
    }


    // =========================================================
    // SHORT TERM
    // =========================================================

    private fun showShortTerm(
        json: JSONObject
    ) {

        val status =
            json.optString(
                "status",
                ""
            )


        content.addView(
            makeText(
                "🔥 فرصت‌های برتر کوتاه‌مدت",
                22f
            )
        )


        if (
            status != "ok"
        ) {

            content.addView(
                makeText(
                    json.optString(
                        "message",
                        "داده کوتاه‌مدت هنوز آماده نیست."
                    ),
                    15f,
                    secondaryColor
                )
            )

            return
        }


        val opportunities =
            json.optJSONArray(
                "opportunities"
            )


        if (
            opportunities == null
            || opportunities.length() == 0
        ) {

            content.addView(
                makeText(
                    "هنوز فرصت کوتاه‌مدتی آماده نشده است.",
                    15f,
                    secondaryColor
                )
            )

            return
        }


        for (
            i in 0 until opportunities.length()
        ) {

            val item =
                opportunities.getJSONObject(i)


            addOpportunityCard(
                item,
                i + 1,
                "کوتاه‌مدت"
            )
        }
    }


    // =========================================================
    // SIX MONTH
    // =========================================================

    private fun showSixMonth(
        json: JSONObject
    ) {

        val status =
            json.optString(
                "status",
                ""
            )


        content.addView(
            makeText(
                "📈 فرصت‌های برتر ۶ ماهه",
                22f
            )
        )


        if (
            status != "ok"
        ) {

            content.addView(
                makeText(
                    json.optString(
                        "message",
                        "داده ۶ ماهه هنوز آماده نیست."
                    ),
                    15f,
                    secondaryColor
                )
            )

            return
        }


        val opportunities =
            json.optJSONArray(
                "opportunities"
            )


        if (
            opportunities == null
            || opportunities.length() == 0
        ) {

            content.addView(
                makeText(
                    "هنوز فرصت ۶ ماهه آماده نشده است.",
                    15f,
                    secondaryColor
                )
            )

            return
        }


        for (
            i in 0 until opportunities.length()
        ) {

            val item =
                opportunities.getJSONObject(i)


            addOpportunityCard(
                item,
                i + 1,
                "۶ ماهه"
            )
        }
    }


    // =========================================================
    // OPPORTUNITY CARD
    // =========================================================

    private fun addOpportunityCard(
        item: JSONObject,
        defaultRank: Int,
        type: String
    ) {

        val card =
            makeCard()


        val rank =
            item.optInt(
                "rank",
                defaultRank
            )


        val ticker =
            item.optString(
                "ticker",
                "---"
            )


        val name =
            item.optString(
                "name",
                "---"
            )


        val sector =
            item.optString(
                "sector",
                "---"
            )


        val score =
            item.optInt(
                "score",
                item.optInt(
                    "rank_score",
                    0
                )
            )


        val currentPrice =
            item.opt(
                "current_price"
            )


        val change =
            item.opt(
                "change_percent"
            )


        val tradeValue =
            item.opt(
                "trade_value"
            )


        val marketCap =
            item.opt(
                "market_cap"
            )


        val pe =
            if (
                item.isNull("pe")
            ) {

                "---"

            } else {

                item.optString(
                    "pe",
                    "---"
                )
            }


        val reasons =
            item.optJSONArray(
                "reasons"
            )


        val reasonsText =
            getReasonsText(
                reasons
            )


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
                "🎯 نوع تحلیل: $type",
                14f,
                secondaryColor
            )
        )


        // ---------------------------------------------------------
        // SCORE
        // ---------------------------------------------------------

        card.addView(
            makeText(
                "⭐ امتیاز تحلیلی: $score / 100",
                18f
            )
        )


        if (
            sector.isNotBlank()
        ) {

            card.addView(
                makeText(
                    "بخش: $sector",
                    14f,
                    secondaryColor
                )
            )
        }


        card.addView(
            makeText(
                "قیمت فعلی: ${formatValue(currentPrice)}",
                15f
            )
        )


        card.addView(
            makeText(
                "تغییر امروز: ${formatValue(change)}٪",
                15f
            )
        )


        card.addView(
            makeText(
                "ارزش معاملات: ${formatValue(tradeValue)}",
                14f,
                secondaryColor
            )
        )


        card.addView(
            makeText(
                "ارزش بازار: ${formatValue(marketCap)}",
                14f,
                secondaryColor
            )
        )


        card.addView(
            makeText(
                "P/E: $pe",
                14f,
                secondaryColor
            )
        )


        card.addView(
            makeText(
                "دلایل تحلیل:\n$reasonsText",
                14f,
                secondaryColor
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


        content.addView(
            card,
            params
        )
    }


    // =========================================================
    // REASONS
    // =========================================================

    private fun getReasonsText(
        reasons: JSONArray?
    ): String {

        if (
            reasons == null
            || reasons.length() == 0
        ) {

            return "نیازمند بررسی عمیق‌تر"
        }


        return buildString {

            for (
                i in 0 until reasons.length()
            ) {

                append("• ")

                append(
                    reasons.optString(
                        i
                    )
                )


                if (
                    i <
                    reasons.length() - 1
                ) {

                    append("\n")
                }
            }
        }
    }


    // =========================================================
    // FORMAT VALUE
    // =========================================================

    private fun formatValue(
        value: Any?
    ): String {

        if (
            value == null
            || value == JSONObject.NULL
        ) {

            return "---"
        }


        return when (value) {

            is Double -> {

                if (
                    value % 1.0 == 0.0
                ) {

                    value.toLong()
                        .toString()

                } else {

                    String.format(
                        "%.2f",
                        value
                    )
                }
            }


            is Float -> {

                if (
                    value % 1f == 0f
                ) {

                    value.toLong()
                        .toString()

                } else {

                    String.format(
                        "%.2f",
                        value
                    )
                }
            }


            else -> {

                value.toString()
            }
        }
    }


    // =========================================================
    // ADD CARD
    // =========================================================

    private fun addCard(
        view: View
    ) {

        val params =
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )


        params.setMargins(
            0,
            5,
            0,
            15
        )


        content.addView(
            view,
            params
        )
    }


    // =========================================================
    // SEPARATOR
    // =========================================================

    private fun addSeparator() {

        val separator =
            View(this).apply {

                setBackgroundColor(
                    Color.rgb(
                        45,
                        60,
                        78
                    )
                )
            }


        val params =
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                2
            )


        params.setMargins(
            0,
            20,
            0,
            25
        )


        content.addView(
            separator,
            params
        )
    }


    // =========================================================
    // ERROR
    // =========================================================

    private fun showError(
        message: String
    ) {

        runOnUiThread {

            refreshButton.isEnabled =
                true

            refreshButton.text =
                "🔄 تلاش مجدد"


            content.removeAllViews()


            content.addView(
                makeText(
                    "❌ خطا",
                    23f
                )
            )


            content.addView(
                makeText(
                    message,
                    15f,
                    secondaryColor
                )
            )
        }
    }
}
