"""NS-3 參數說明對話框 — 涵蓋 run_ed_experiments.py / OBSS_3BSS-custom / wifi7-base 所有有效參數。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# ── 資料定義 ──────────────────────────────────────────────────────────────────
# 每一筆：(參數名, 類型/預設值, 說明)

_SCRIPT_PARAMS: list[tuple[str, str, str]] = [
    ("--k",                  "int（預設：CPU/2）",   "平行執行的 worker 執行緒數"),
    ("--num-runs",           "int（預設：30）",       "每個 ED 模式執行的次數"),
    ("--ns3-root",           "Path",                 "包含 ./ns3 執行檔的根目錄路徑"),
    ("--output-dir",         "Path",                 "所有輸出、log、manifest 的存放目錄"),
    ("--scenario",           "str",                  "傳給 ./ns3 run 的場景名稱（預設：thesis-wifi7-OBSS_3BSS-custom）"),
    ("--base-args",          "str",                  "附加在場景名稱後的所有場景參數字串"),
    ("--prefix",             "str（預設：obss3-6g160）", "輸出檔案的名稱前綴"),
    ("--retry",              "int（預設：0）",        "失敗後的重試次數"),
    ("--require-co-bss-all", "flag",                 "要求 co-bss0/1/2-single.csv 全部存在（預設只要求 bss0）"),
    ("--require-co-sta-all", "flag（預設開啟）",     "要求 co-sta0/1/2-single.csv 全部存在"),
    ("--no-require-co-sta-all", "flag",              "關閉 co-sta 輸出檢查"),
]

_CUSTOM_PARAMS: list[tuple[str, str, str]] = [
    # ── 幾何 ──────────────────────────────────────────────────────────────
    ("apXyBss0",    "x:y 字串",  "BSS0 AP 絕對座標；三個 apXyBss* 需同時設定"),
    ("apXyBss1",    "x:y 字串",  "BSS1 AP 絕對座標"),
    ("apXyBss2",    "x:y 字串",  "BSS2 AP 絕對座標"),
    ("staPolarBss0","dist@deg,…","BSS0 各 STA 相對 AP 的距離與角度（極座標列表）"),
    ("staPolarBss1","dist@deg,…","BSS1 各 STA 極座標列表"),
    ("staPolarBss2","dist@deg,…","BSS2 各 STA 極座標列表"),
    ("triSide",     "float（m）","三角形邊長，使用絕對座標時僅作 CSV/log label 用"),
    # ── 鏈路 / 頻道 ────────────────────────────────────────────────────────
    ("enabledLinks",       "comma list（如 0,1,2）","全域啟用的鏈路集合（0=2.4G, 1=5G, 2=6G）"),
    ("linkSteeringMode",   "none|fixed|split",      "鏈路轉向模式（預設：none）"),
    ("linkSteeringDynamic","0|1",                   "啟用動態 split 更新"),
    ("bssLinks0",          "comma list",             "BSS0 使用的鏈路集合"),
    ("bssLinks1",          "comma list",             "BSS1 使用的鏈路集合"),
    ("bssLinks2",          "comma list",             "BSS2 使用的鏈路集合"),
    ("coUpdateMs",         "int（ms）",             "動態鏈路更新週期"),
    ("coEmaAlpha",         "float",                 "動態 EMA 平滑係數"),
    ("chWidth24",          "int MHz（預設：20）",   "2.4 GHz 頻道寬度"),
    ("chWidth5",           "int MHz（預設：80）",   "5 GHz 頻道寬度"),
    ("chWidth6",           "int MHz（預設：160）",  "6 GHz 頻道寬度"),
    # ── 傳播模型 ──────────────────────────────────────────────────────────
    ("refLoss24",          "float dB",  "2.4 GHz LogDistance 參考損耗"),
    ("refLoss5",           "float dB",  "5 GHz LogDistance 參考損耗"),
    ("refLoss6",           "float dB",  "6 GHz LogDistance 參考損耗"),
    ("pathLossExp24",      "float",     "2.4 GHz 路徑損耗指數"),
    ("pathLossExp5",       "float",     "5 GHz 路徑損耗指數"),
    ("pathLossExp6",       "float",     "6 GHz 路徑損耗指數"),
    # ── MCS / 速率 ────────────────────────────────────────────────────────
    ("mcsIndex",           "int 0-13",  "BSS0 MCS index（ConstantRateWifiManager）"),
    ("mcsBss1",            "int 0-13（預設：13）","BSS1 MCS index"),
    ("mcsBss2",            "int 0-13（預設：13）","BSS2 MCS index"),
    ("rateManagerType",    "str",       "BSS0 速率管理器類型（預設：ConstantRate）"),
    ("rateManagerTypeBss1","str",       "BSS1 速率管理器類型"),
    ("rateManagerTypeBss2","str",       "BSS2 速率管理器類型"),
    # ── 流量 ──────────────────────────────────────────────────────────────
    ("time",               "int s",     "模擬總時長"),
    ("appStart",           "int s",     "OnOff app 啟動時間"),
    ("offeredLoad",        "str（如 717Mbps）","BSS0 OnOff 提供流量"),
    ("offeredLoadBss1",    "str",       "BSS1 OnOff 提供流量"),
    ("offeredLoadBss2",    "str",       "BSS2 OnOff 提供流量"),
    ("giNs",               "800|1600|3200","Guard Interval（ns）"),
    ("nss",                "int 1-4",   "空間串流數"),
    ("pktSize",            "int bytes", "OnOff 封包大小"),
    ("startJitterMaxMs",   "int ms",    "應用程式啟動抖動上限"),
    ("onTime",             "float s",   "OnOff on-time"),
    ("offTime",            "float s",   "OnOff off-time"),
    ("onTimeDist",         "constant|exponential","on-time 分佈"),
    ("offTimeDist",        "constant|exponential","off-time 分佈"),
    # ── 量測 ──────────────────────────────────────────────────────────────
    ("settleTimeSec",        "float s（預設：2.0）","appStop 後額外等待時間（clamped 1-5）"),
    ("perCountUnknownAsError","0|1（預設：1）",     "將 Unknown 解碼結果計為錯誤"),
    # ── Tracing：PHY failure ───────────────────────────────────────────────
    ("phyFailureStats",      "0|1（預設：1）","啟用 PHY failure 統計輸出"),
    ("sinrPercentiles",      "0|1（預設：1）","啟用 SINR 百分位數輸出"),
    ("phyFailureEventLog",   "0|1（預設：0）","逐事件記錄 PHY failure"),
    ("phyFailureEventLogBss","0-2（預設：0）","指定記錄哪個 BSS 的 PHY failure（需 EventLog=1）"),
    # ── Tracing：Packet SINR Tracker ─────────────────────────────────────
    ("packetSinrTracker",   "0|1（預設：0）","啟用 PacketSinrTracker（主開關）"),
    ("packetSinrWindowMs",  "int ms（預設：20）","滑動視窗大小（需 tracker=1）"),
    ("packetSinrEventLog",  "0|1（預設：0）","輸出逐 PPDU raw event CSV（需 tracker=1）"),
    ("packetSinrWindowCsv", "0|1（預設：1）","輸出滑動視窗摘要 CSV（需 tracker=1）"),
    ("packetSinrApRawEvent","0|1（預設：0）","額外監聽 AP 端 raw event（需 tracker=1）"),
]

_BASE_PARAMS: list[tuple[str, str, str]] = [
    # ── 輸出 ──────────────────────────────────────────────────────────────
    ("outputFileName",     "str",          "輸出檔案名稱前綴（由腳本的 --prefix 控制，通常不需手動設定）"),
    ("pcap",               "0|1（預設：0）","啟用 PCAP 封包捕獲"),
    # ── PHY ───────────────────────────────────────────────────────────────
    ("ldpc",               "0|1（預設：1）","啟用 LDPC FEC 編碼（0=BCC）"),
    ("useEdOnlyOnPreambleDetectFailure","0|1","Energy Detection 僅在 Preamble 偵測失敗時作為 CCA 依據"),
    ("rxNoiseFigureDb",    "float dB",     "接收機雜訊指數，影響熱雜訊底限計算"),
    # ── SNR Trace（wifi7-base）────────────────────────────────────────────
    ("snrTrace",           "0|1（預設：1）","啟用 PHY MonitorSnifferRx SNR tracing"),
    ("snrDataOnly",        "0|1（預設：0）","SNR trace 只統計 Data/QoS Data frame"),
    ("snrTarget",          "0-2（預設：0）","SNR trace 目標：0=STA, 1=AP, 2=ALL"),
    ("snrPerDevice",       "0|1（預設：0）","SNR trace 按裝置個別統計"),
    ("snrPerChannel",      "0|1（預設：0）","SNR trace 按頻道（channelFreqMhz）個別統計"),
    ("snrRxModeHist",      "0|1（預設：0）","SNR trace 收集 Rx mode 直方圖"),
]


# ── Dialog ──────────────────────────────────────────────────────────────────

class Ns3ParamsDialog(QDialog):
    """NS-3 可用參數說明對話框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NS-3 參數說明")
        self.setMinimumWidth(780)
        self.setMinimumHeight(560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QLabel("<b>NS-3 可用參數說明</b>　（Italic = 由 Network Planner 自動填入）")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        tabs = QTabWidget()

        tabs.addTab(
            _make_table(_SCRIPT_PARAMS, col0_header="腳本參數"),
            "📜  run_ed_experiments.py",
        )
        tabs.addTab(
            _make_table(_CUSTOM_PARAMS, col0_header="--base-args 參數"),
            "🎯  OBSS_3BSS-custom",
        )
        tabs.addTab(
            _make_table(_BASE_PARAMS, col0_header="繼承自 wifi7-base"),
            "🏗  wifi7-base（繼承）",
        )

        layout.addWidget(tabs)

        note = QLabel(
            "<small style='color:gray;'>"
            "* 被 custom 腳本標示為 Ignored 的舊參數（apStaDist, staPerBss, "
            "staPlacement, obssRange, distMin, distMax, distStep, repeat）不在此列表中。"
            "</small>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def _make_table(rows: list[tuple[str, str, str]], col0_header: str) -> QTableWidget:
    table = QTableWidget(len(rows), 3)
    table.setHorizontalHeaderLabels([col0_header, "類型 / 預設值", "說明"])
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setAlternatingRowColors(True)
    table.setWordWrap(True)

    for row_idx, (param, typ, desc) in enumerate(rows):
        for col, text in enumerate((param, typ, desc)):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col == 0:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            elif col == 1:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_idx, col, item)

    table.resizeRowsToContents()
    return table
