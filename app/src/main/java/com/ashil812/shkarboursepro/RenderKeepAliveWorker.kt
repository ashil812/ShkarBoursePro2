package com.ashil812.shkarboursepro

import android.content.Context
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.net.HttpURLConnection
import java.net.URL


class RenderKeepAliveWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : Worker(
    appContext,
    workerParams
) {

    private val healthUrl =
        "https://shkar-bourse-pro2.onrender.com/health"


    override fun doWork(): Result {

        var connection:
            HttpURLConnection? = null


        return try {

            val url =
                URL(healthUrl)


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


            if (
                responseCode in 200..299
            ) {

                Result.success()

            } else {

                Result.retry()
            }


        } catch (
            e: Exception
        ) {

            Result.retry()

        } finally {

            connection?.disconnect()
        }
    }
}
