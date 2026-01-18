import os
from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Vinted URL: change the TLD according to your country (.fr, .es, etc.)
vinted_url = "https://www.vinted.fr"

# Vinted queries for research
# "page", "per_page" and "order" you may not edit them
# "search_text" is the free search field, this field may be empty if you wish to search for the entire brand.
# "catalog_ids" is the category in which to eventually search, if the field is empty it will search in all categories. Vinted assigns a numeric ID to each category, e.g. 2996 is the ID for e-Book Reader
# "brand_ids" if you want to search by brand. Vinted assigns a numeric ID to each brand, e.g. 417 is the ID for Louis Vuitton
# "order" you can change it to relevance, newest_first, price_high_to_low, price_low_to_high

queries = [
    {
        'page': '1',
        'per_page': '96',
        'search_text': 'keyonte',
	    'title_filters': [
		    'keyonte',
		    'george'
	    ],
        'catalog_ids': '',
        'brand_ids' : '',
        'order': 'newest_first',
	    'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_KEYONTE")
    },
	{
		'page': '1',
		'per_page': '96',
		'search_text': 'sensabaugh',
		'title_filters': [
			'brice',
			'sensabaugh'
		],
		'catalog_ids': '',
		'brand_ids': '',
		'order': 'newest_first',
		'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_BRICE")
	},
	{
		'page': '1',
		'per_page': '96',
		'search_text': 'donovan mitchell',
		'title_filters': [
			'donovan',
			'mitchell'
		],
		'catalog_ids': '',
		'brand_ids': '',
		'order': 'newest_first',
		'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_DONOVAN")
	},
	{
		'page': '1',
		'per_page': '96',
		'search_text': 'isaiah collier',
		'title_filters': [
			'isaiah',
			'collier'
		],
		'catalog_ids': '',
		'brand_ids': '',
		'order': 'newest_first',
		'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_ISAIAH")
	},
	{
		'page': '1',
		'per_page': '96',
		'search_text': 'jaylon tyson',
		'title_filters': [
			'jaylon',
			'tyson'
		],
		'catalog_ids': '',
		'brand_ids': '',
		'order': 'newest_first',
		'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_JAYLON")
	},
	{
		'page': '1',
		'per_page': '96',
		'search_text': 'doncic',
		'title_filters': [
			'luka',
			['doncic', 'dončić', 'doncić'],
			['rc', 'rooki', 'rookie']
		],
		'catalog_ids': '',
		'brand_ids': '',
		'order': 'newest_first',
		'discord_channel_id': os.getenv("DISCORD_CHANNEL_ID_LUKA_RC")
	},
]
