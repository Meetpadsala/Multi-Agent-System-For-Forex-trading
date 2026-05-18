"""
Central configuration for all currency pairs supported by the trading system.
This includes Major, Minor, and Exotic pairs as per Forex market standards.
"""

# Major Currency Pairs (7 Most Liquid - Include USD)
MAJOR_PAIRS = [
    'EURUSD',  # Euro / US Dollar
    'USDJPY',  # US Dollar / Japanese Yen
    'GBPUSD',  # British Pound / US Dollar
    'USDCHF',  # US Dollar / Swiss Franc
    'AUDUSD',  # Australian Dollar / US Dollar
    'USDCAD',  # US Dollar / Canadian Dollar
    'NZDUSD',  # New Zealand Dollar / US Dollar
]

# Minor Pairs - EUR Crosses (No USD)
EUR_CROSSES = [
    'EURGBP',  # Euro / British Pound
    'EURJPY',  # Euro / Japanese Yen
    'EURCHF',  # Euro / Swiss Franc
    'EURAUD',  # Euro / Australian Dollar
    'EURCAD',  # Euro / Canadian Dollar
    'EURNZD',  # Euro / New Zealand Dollar
    'EURSEK',  # Euro / Swedish Krona
    'EURNOK',  # Euro / Norwegian Krone
    'EURDKK',  # Euro / Danish Krone
    'EURPLN',  # Euro / Polish Zloty
    'EURHUF',  # Euro / Hungarian Forint
    'EURCZK',  # Euro / Czech Koruna
    'EURTRY',  # Euro / Turkish Lira
    'EURZAR',  # Euro / South African Rand
]

# Minor Pairs - GBP Crosses (No USD)
GBP_CROSSES = [
    'GBPJPY',  # British Pound / Japanese Yen
    'GBPCHF',  # British Pound / Swiss Franc
    'GBPAUD',  # British Pound / Australian Dollar
    'GBPCAD',  # British Pound / Canadian Dollar
    'GBPNZD',  # British Pound / New Zealand Dollar
    'GBPSEK',  # British Pound / Swedish Krona
    'GBPNOK',  # British Pound / Norwegian Krone
    'GBPDKK',  # British Pound / Danish Krone
    'GBPPLN',  # British Pound / Polish Zloty
    'GBPTRY',  # British Pound / Turkish Lira
    'GBPZAR',  # British Pound / South African Rand
]

# Minor Pairs - JPY Crosses
JPY_CROSSES = [
    'AUDJPY',  # Australian Dollar / Japanese Yen
    'CADJPY',  # Canadian Dollar / Japanese Yen
    'CHFJPY',  # Swiss Franc / Japanese Yen
    'NZDJPY',  # New Zealand Dollar / Japanese Yen
    'SEKJPY',  # Swedish Krona / Japanese Yen
    'NOKJPY',  # Norwegian Krone / Japanese Yen
    'ZARJPY',  # South African Rand / Japanese Yen
    'TRYJPY',  # Turkish Lira / Japanese Yen
    'SGDJPY',  # Singapore Dollar / Japanese Yen
    'HKDJPY',  # Hong Kong Dollar / Japanese Yen
]

# Minor Pairs - Other Crosses
OTHER_CROSSES = [
    'AUDCAD',  # Australian Dollar / Canadian Dollar
    'AUDCHF',  # Australian Dollar / Swiss Franc
    'AUDNZD',  # Australian Dollar / New Zealand Dollar
    'AUDSGD',  # Australian Dollar / Singapore Dollar
    'AUDHKD',  # Australian Dollar / Hong Kong Dollar
    'CADCHF',  # Canadian Dollar / Swiss Franc
    'CADNZD',  # Canadian Dollar / New Zealand Dollar
    'CHFSGD',  # Swiss Franc / Singapore Dollar
    'NZDCHF',  # New Zealand Dollar / Swiss Franc
    'NZDCAD',  # New Zealand Dollar / Canadian Dollar
    'SGDCHF',  # Singapore Dollar / Swiss Franc
]

# Exotic Pairs - USD with Emerging Currencies
USD_EXOTICS = [
    'USDINR',  # US Dollar / Indian Rupee
    'USDCNY',  # US Dollar / Chinese Yuan
    'USDHKD',  # US Dollar / Hong Kong Dollar
    'USDSGD',  # US Dollar / Singapore Dollar
    'USDKRW',  # US Dollar / South Korean Won
    'USDTHB',  # US Dollar / Thai Baht
    'USDMYR',  # US Dollar / Malaysian Ringgit
    'USDIDR',  # US Dollar / Indonesian Rupiah
    'USDPHP',  # US Dollar / Philippine Peso
    'USDTWD',  # US Dollar / Taiwan Dollar
    'USDVND',  # US Dollar / Vietnamese Dong
    'USDPKR',  # US Dollar / Pakistani Rupee
    'USDBDT',  # US Dollar / Bangladeshi Taka
    'USDLKR',  # US Dollar / Sri Lankan Rupee
    'USDAED',  # US Dollar / UAE Dirham
    'USDSAR',  # US Dollar / Saudi Riyal
    'USDQAR',  # US Dollar / Qatari Riyal
    'USDKWD',  # US Dollar / Kuwaiti Dinar
    'USDOMR',  # US Dollar / Omani Rial
    'USDBHD',  # US Dollar / Bahraini Dinar
    'USDILS',  # US Dollar / Israeli Shekel
    'USDZAR',  # US Dollar / South African Rand
    'USDNGN',  # US Dollar / Nigerian Naira
    'USDEGP',  # US Dollar / Egyptian Pound
    'USDMXN',  # US Dollar / Mexican Peso
    'USDBRL',  # US Dollar / Brazilian Real
    'USDCLP',  # US Dollar / Chilean Peso
    'USDCOP',  # US Dollar / Colombian Peso
    'USDPEN',  # US Dollar / Peruvian Sol
    'USDARS',  # US Dollar / Argentine Peso
    'USDTRY',  # US Dollar / Turkish Lira
    'USDRUB',  # US Dollar / Russian Ruble
    'USDUAH',  # US Dollar / Ukrainian Hryvnia
    'USDKZT',  # US Dollar / Kazakhstani Tenge
]

# Additional Actively Traded Pairs
ADDITIONAL_PAIRS = [
    'EURMXN',  # Euro / Mexican Peso
    'EURSGD',  # Euro / Singapore Dollar
    'EURHKD',  # Euro / Hong Kong Dollar
    'EURILS',  # Euro / Israeli Shekel
    'EURRUB',  # Euro / Russian Ruble
    'GBPMXN',  # British Pound / Mexican Pound
    'GBPSGD',  # British Pound / Singapore Dollar
    'GBPHKD',  # British Pound / Hong Kong Dollar
    'GBPILS',  # British Pound / Israeli Shekel
    'AUDMXN',  # Australian Dollar / Mexican Peso
    'CADMXN',  # Canadian Dollar / Mexican Peso
    'CHFZAR',  # Swiss Franc / South African Rand
    'NZDSGD',  # New Zealand Dollar / Singapore Dollar
    'SGDHKD',  # Singapore Dollar / Hong Kong Dollar
    'HKDCNH',  # Hong Kong Dollar / Chinese Yuan (Offshore)
]

# All currency pairs combined
ALL_PAIRS = (
    MAJOR_PAIRS + 
    EUR_CROSSES + 
    GBP_CROSSES + 
    JPY_CROSSES + 
    OTHER_CROSSES + 
    USD_EXOTICS + 
    ADDITIONAL_PAIRS
)

# Base prices for mock data generation
# These are approximate prices for generating realistic mock data
BASE_PRICES = {
    # Major Pairs
    'EURUSD': 1.0800,
    'USDJPY': 150.00,
    'GBPUSD': 1.2700,
    'USDCHF': 0.8800,
    'AUDUSD': 0.6500,
    'USDCAD': 1.3600,
    'NZDUSD': 0.6100,
    
    # EUR Crosses
    'EURGBP': 0.8500,
    'EURJPY': 162.00,
    'EURCHF': 0.9500,
    'EURAUD': 1.6600,
    'EURCAD': 1.4700,
    'EURNZD': 1.7700,
    'EURSEK': 11.20,
    'EURNOK': 11.50,
    'EURDKK': 7.4500,
    'EURPLN': 4.3200,
    'EURHUF': 385.00,
    'EURCZK': 24.50,
    'EURTRY': 32.50,
    'EURZAR': 19.80,
    
    # GBP Crosses
    'GBPJPY': 190.50,
    'GBPCHF': 1.1200,
    'GBPAUD': 1.9500,
    'GBPCAD': 1.7300,
    'GBPNZD': 2.0800,
    'GBPSEK': 13.20,
    'GBPNOK': 13.50,
    'GBPDKK': 8.7800,
    'GBPPLN': 5.0900,
    'GBPTRY': 38.20,
    'GBPZAR': 23.30,
    
    # JPY Crosses
    'AUDJPY': 97.50,
    'CADJPY': 110.20,
    'CHFJPY': 170.50,
    'NZDJPY': 91.50,
    'SEKJPY': 14.50,
    'NOKJPY': 13.80,
    'ZARJPY': 9.60,
    'TRYJPY': 4.85,
    'SGDJPY': 112.00,
    'HKDJPY': 19.20,
    
    # Other Crosses
    'AUDCAD': 0.8840,
    'AUDCHF': 0.5720,
    'AUDNZD': 1.0650,
    'AUDSGD': 0.5400,
    'AUDHKD': 5.0700,
    'CADCHF': 0.6470,
    'CADNZD': 1.2050,
    'CHFSGD': 1.7200,
    'NZDCHF': 0.5360,
    'NZDCAD': 0.8300,
    'SGDCHF': 0.5800,
    
    # USD Exotics
    'USDINR': 83.00,
    'USDCNY': 7.2000,
    'USDHKD': 7.8100,
    'USDSGD': 1.3400,
    'USDKRW': 1320.00,
    'USDTHB': 35.50,
    'USDMYR': 4.7200,
    'USDIDR': 15600.00,
    'USDPHP': 55.80,
    'USDTWD': 31.50,
    'USDVND': 24350.00,
    'USDPKR': 278.00,
    'USDBDT': 110.00,
    'USDLKR': 325.00,
    'USDAED': 3.6725,
    'USDSAR': 3.7500,
    'USDQAR': 3.6400,
    'USDKWD': 0.3080,
    'USDOMR': 0.3850,
    'USDBHD': 0.3770,
    'USDILS': 3.6500,
    'USDZAR': 18.50,
    'USDNGN': 1550.00,
    'USDEGP': 30.90,
    'USDMXN': 17.15,
    'USDBRL': 4.9700,
    'USDCLP': 925.00,
    'USDCOP': 3950.00,
    'USDPEN': 3.7200,
    'USDARS': 865.00,
    'USDTRY': 32.00,
    'USDRUB': 92.50,
    'USDUAH': 37.50,
    'USDKZT': 450.00,
    
    # Additional Pairs
    'EURMXN': 18.50,
    'EURSGD': 1.4480,
    'EURHKD': 8.4400,
    'EURILS': 3.9400,
    'EURRUB': 100.00,
    'GBPMXN': 21.80,
    'GBPSGD': 1.7000,
    'GBPHKD': 9.9200,
    'GBPILS': 4.6300,
    'AUDMXN': 11.15,
    'CADMXN': 12.60,
    'CHFZAR': 21.00,
    'NZDSGD': 0.8200,
    'SGDHKD': 5.8300,
    'HKDCNH': 0.9200,
}

# Sentiment mapping for pairs (for SentimentAgent)
# Default sentiment is NEUTRAL
SENTIMENT_MAP = {
    'EURUSD': 'POSITIVE',
    'GBPUSD': 'NEGATIVE',
    'USDJPY': 'NEUTRAL',
    'USDINR': 'POSITIVE',
    'AUDUSD': 'NEUTRAL',
    'USDCAD': 'POSITIVE',
    'USDCHF': 'NEGATIVE',
    'NZDUSD': 'NEUTRAL',
    'EURGBP': 'NEUTRAL',
    'EURJPY': 'POSITIVE',
    'GBPJPY': 'NEGATIVE',
    'USDZAR': 'POSITIVE',
    'USDTRY': 'NEGATIVE',
    'USDMXN': 'NEUTRAL',
    'USDBRL': 'POSITIVE',
}


def get_all_pairs():
    """Return list of all supported currency pairs"""
    return ALL_PAIRS


def get_base_price(symbol):
    """Return base price for a symbol, or default 1.0 if not found"""
    return BASE_PRICES.get(symbol, 1.0)


def get_sentiment(symbol):
    """Return sentiment for a symbol"""
    return SENTIMENT_MAP.get(symbol, 'NEUTRAL')


def is_valid_pair(symbol):
    """Check if a symbol is a valid supported pair"""
    return symbol in ALL_PAIRS
