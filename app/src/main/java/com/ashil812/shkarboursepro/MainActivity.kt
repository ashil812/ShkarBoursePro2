package com.ashil812.shkarboursepro

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {

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

        val marketTitle = text("📊 وضعیت بازار", 20f)
        content.addView(marketTitle)

        val marketCard = text(
            "در حال دریافت اطلاعات بازار...\n\n" +
            "شاخص کل: ---\n" +
            "ارزش معاملات: ---\n" +
            "وضعیت بازار: در انتظار داده",
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

        content.addView(text("🔥 بهترین فرصت‌ها", 20f))

        val opportunity = text(
            "هنوز داده‌ای برای تحلیل دریافت نشده است.\n\n" +
            "پس از اتصال داده‌های بورس، سیستم تمام نمادها را بررسی کرده و " +
            "فرصت‌های پرپتانسیل را رتبه‌بندی می‌کند.",
            16f
        )

        opportunity.setBackgroundColor(Color.rgb(24, 36, 52))

        content.addView(
            opportunity,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins(0, 10, 0, 25)
            }
        )

        content.addView(text("🎯 سیستم امتیازدهی", 20f))

        val score = text(
            "امتیاز هر سهم بر اساس مجموعه‌ای از معیارهای تکنیکال، " +
            "حجم معاملات، مومنتوم و رفتار قیمت محاسبه خواهد شد.",
            16f
        )

        score.setBackgroundColor(Color.rgb(24, 36, 52))
        content.addView(score)

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
    }
}
