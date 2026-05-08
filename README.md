# Algorithmic Trading

This is a strategy taken from Alapca's example but modified to be intraday. However,
it is very conservation. Long trades are made only during an up-trend and short trades
are made during a down-trend. This way you don't end up taking a long position a.k.a 
catching a knife due to RSI bounce from oversold during a down-trend a.k.a dead cat bounce. 

## Rules
- Timeframes:
   MAIN  (1-min)  : RSI + MACD signals are computed here.
   TREND (30-min) : Three moving averages define whether we're in an up- or
                    down-trend. We only trade in the direction of the trend.

- LONG trade (uptrend: MA20 > MA50 > MA100 on 30-min bars):
   Entry   RSI crosses UP through 30 (oversold bounce)
             AND MACD golden cross (MACD line crosses above Signal)
             Both events must occur within WINDOW_SIZE bars of each other.
   Exit    RSI drops below 65 from above 70 (overbought retreat)
             AND (MACD death cross OR MACD drops below zero)
             Both events must occur within WINDOW_SIZE bars of each other.

- SHORT trade (downtrend: MA20 < MA50 < MA100 on 30-min bars):
   Entry  RSI crosses DOWN through 70 (overbought peak)
             AND MACD death cross (MACD line crosses below Signal)
             Both events must occur within WINDOW_SIZE bars of each other.
   Exit    RSI rises above 35 from below 30 (oversold bounce)
             AND (MACD golden cross OR MACD rises above zero)
             Both events must occur within WINDOW_SIZE bars of each other.




First, clone the repo

```console
foo@bar:~$ git clone git@github.com:lkscodediary/algotrading.git --single-branch --branch main algo
```
#### Setup venv
Open your console and navigate to the folder and run the following commands
```console
foo@bar:~$ cd algo
foo@bar:$ python3 -m venv venv
foo@bar:$ source venv/bin/activate
(venv) foo@bar:$ pip install -r resources/requirements.txt
```
#### Run App
```console
(venv) foo@bar:$ python app.py
```
