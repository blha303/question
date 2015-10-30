Question
========

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

A Flask web server for quickly asking someone a question. Uses [Airgram](http://www.airgramapp.com) for push notification functionality, so users need to make accounts there.

Currently backend JSON api only. Feel free to implement your own frontend around the API using your own instance.

The lines starting with "Question from" are sent first, at the same time. The user swipes or selects the relevant option, and a reply is sent to the user indicating their choice. In the below example, I used my own username for both.

![screenshot](http://i.imgur.com/MXTWZY8.png)
