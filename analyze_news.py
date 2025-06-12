import os
import psycopg2
import openai
import json
from dotenv import load_dotenv
from datetime import date, timedelta
import time
import httpx

# .env 파일에서 API 키 불러오기
load_dotenv()

# 2. SSL 검증을 비활성화하는 커스텀 HTTP 클라이언트 생성
# 회사 네트워크에서 SSL 인증서 문제 우회 목적 
custom_http_client = httpx.Client(verify=False)

# 3. 커스텀 클라이언트를 사용하여 OpenAI 클라이언트 인스턴스 생성
client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

# 데이터베이스 연결 정보 (
db_conn_info = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

# ---------------- [ Few-shot 예시 데이터 정의 시작 ] ----------------
# 각 품목별로 예시를 구조화하여 저장합니다.
FEW_SHOT_EXAMPLES = {
    # --- Corn Examples ---
    "Corn": [
        {
            "article": "U.S. corn futures surged on Thursday, July 19, 2012, as the worst drought in over half a century continued to bake key growing regions. December corn futures (ZCZ12) on the Chicago Board of Trade reportedly climbed to an all-time high, settling up by the daily trading limit of 40 cents at $7.99 1/4 per bushel (some reports indicated intraday highs above $8). The USDA had sharply cut its production forecast earlier in the month, and relentless heat with no rain in sight intensified fears of catastrophic yield losses.",
            "output": {
                "sentiment_score": 96,
                "reasoning": "US drought: major corn supply cut expected (Supply↓). Unexpected severity led to record high/limit up (Mag: Extreme). Intensified prior bull trend. Severe supply shock warrants 96.",
                "keywords": ["US Drought 2012", "Corn Price Record High", "Supply Shock", "LimitUp", "ExtremePositive", "CropFailure"]
            }
        },
        {
            "article": "Chicago corn futures plummeted on Friday, June 28, 2013, after the U.S. Department of Agriculture released shockingly bearish Acreage and Grain Stocks reports. The USDA reported corn planted area at 97.38 million acres, significantly above average trade estimates and even its own March forecast. Quarterly grain stocks were also much larger than anticipated. December corn futures (ZCZ13) fell by the daily trading limit of 40 cents, settling near $4.70 per bushel, a drop of approximately 7-8%.",
            "output": {
                "sentiment_score": 5,
                "reasoning": "USDA reports: extreme bearish shock. Far higher acreage/stocks (Supply↑↑) signal glut. Unexpectedly large figures (Exp: Very High) caused limit down (Mag: Extreme). Supply shock justifies 5.",
                "keywords": ["USDA Report Shock", "Corn Acreage Surprise", "Grain Stocks Bearish", "LimitDown", "ExtremeNegative", "SupplyGlutFear"]
            }
        },
        {
            "article": "U.S. corn futures rallied by over 3% on Tuesday, May 10, 2022, after the USDA's monthly WASDE report projected lower-than-expected U.S. corn ending stocks for the upcoming marketing year. The reduction was attributed to a slight decrease in forecast production due to delayed plantings and an increase in projected export demand, signaling a tighter domestic balance sheet than previously anticipated by traders.",
            "output": {
                "sentiment_score": 78,
                "reasoning": "USDA WASDE: bullish surprise with lower US ending stocks (Supply↓, Demand↑). Unexpectedly tight balance (Exp: High). 3%+ rally (Mag: Significant). Supply tightening justifies 78.",
                "keywords": ["USDA WASDE Report", "Corn Ending Stocks Lowered", "ExportDemandUp", "BullishSurprise", "VeryPositive"]
            }
        },
        {
            "article": "Chicago corn futures eased around 2% on Monday, July 17, 2023, as weekend rains across key U.S. Corn Belt areas improved soil moisture conditions for the developing crop. Weekly USDA crop progress reports also showed a slight improvement in good-to-excellent ratings, alleviating some earlier concerns about drought stress impacting yield potential.",
            "output": {
                "sentiment_score": 40,
                "reasoning": "US Corn Belt rains improve crop conditions (Supply↑ outlook). Expected weather shift eases drought fears. 2% dip (Mag: Moderate) reflects reduced supply concerns. Improved supply outlook, 40.",
                "keywords": ["Favorable Weather", "Corn Crop Conditions Improve", "Rainfall Midwest", "SupplyOutlookBetter", "MildlyNegative"]
            }
        }
    ],
    # --- Wheat Examples ---
    "Wheat": [
        {
            "article": "Global wheat prices surged dramatically on Thursday, August 5, 2010, after Russia, then one of the world's largest wheat exporters, announced an immediate ban on grain exports following a severe drought and widespread wildfires that devastated its harvest. Chicago Board of Trade September wheat futures rocketed up by the daily trading limit of 60 cents to settle at $7.85 3/4 per bushel, an 8.3% increase. December wheat also hit limit-up.",
            "output": {
                "sentiment_score": 97,
                "reasoning": "Russia's wheat export ban: extreme global shock. Major exporter's supply instantly lost (Supply↓↓), causing severe deficit. Unexpected ban (Exp: Very High) led to limit up (Mag: Extreme). Supply crisis, 97.",
                "keywords": ["Russian Wheat Export Ban", "Drought", "Global Supply Shock", "LimitUp", "ExtremePositive", "FoodSecurityConcern"]
            }
        },
        {
            "article": "U.S. wheat futures tumbled sharply on Friday, July 12, 2014, with the December contract falling by over 5%, after the USDA's monthly supply and demand report projected a larger-than-expected increase in global wheat ending stocks. The report highlighted record production forecasts in several key exporting countries and a slight downward revision in global consumption, painting a picture of ample world supplies.",
            "output": {
                "sentiment_score": 8,
                "reasoning": "USDA report: major bearish shock. Much larger global stocks projected (Supply↑↑) on record output. Unexpectedly large surplus (Exp: High), prices -5% (Mag: Extreme). Global glut confirmed, 8.",
                "keywords": ["USDA Report Bearish", "Global Wheat Surplus", "Record Production", "WheatPricePlunge", "ExtremeNegative", "Oversupply"]
            }
        },
        {
            "article": "Chicago wheat futures jumped more than 4% on October 13, 2021, after a USDA report unexpectedly cut its forecast for U.S. spring wheat production due to drought conditions in the Northern Plains. The report also showed lower-than-anticipated domestic wheat stocks, suggesting a tighter U.S. supply situation than the market had factored in.",
            "output":{
                "sentiment_score":80,
                "reasoning":"USDA report: bullish. Unexpected US spring wheat production cut & lower stocks (Supply↓). Surprise tight supply (Exp: High). 4%+ rally (Mag: Strong). US supply squeeze warrants 80.",
                "keywords":["USDA Report Bullish", "US Wheat Production Cut", "Wheat Stocks Lower", "SupplyTightness", "VeryPositive"]
            }
        },
        {
            "article": "Wheat market consolidating; traders assessing global export competition and mixed weather forecasts.",
            "output":{
                "sentiment_score":42,
                "reasoning":"Beneficial US rains (Supply↑ outlook) & Black Sea export competition pressure prices. Expected weather impact, ongoing rivalry. 1.5% dip (Mag: Modest). Improved supply, competition weigh; 42.",
                "keywords":["Favorable US Weather", "Black Sea Export Competition", "WheatPriceEase", "MildlyNegative"]
            }
        }     
    ],
    # --- WTI Crude Oil Examples ---
    "WTI Crude Oil": [
        {
            "article": "Oil prices surged dramatically on Monday, September 16, 2019, after coordinated drone attacks on key Saudi Arabian oil infrastructure over the weekend. WTI crude futures jumped by as much as 15.5% to $63.34 per barrel, the largest intraday percentage gain since 2008. The attacks reportedly crippled about 5.7 million barrels per day of Saudi Arabia's production, equivalent to over 5% of global daily oil supply.",
            "output": {
                "sentiment_score": 95,
                "reasoning": "Saudi facility attack: severe supply shock (5.7M bpd down). Highly unexpected (Exp: Very Low), WTI surged 15.5% (Mag: Very High). Overwhelms prior neutral context. Extreme supply loss justifies 95.",
                "keywords": ["Saudi Aramco Attack", "Oil Supply Disruption", "WTI Price Surge", "Geopolitical Shock", "ExtremePositive", "HistoricalHighVolatility"]
            }
        },
        {
            "article": "West Texas Intermediate (WTI) crude oil for May delivery experienced an unprecedented collapse on Monday, April 20, 2020, plunging deep into negative territory for the first time in history. The May contract (CLK20) settled at -$37.63 a barrel, a drop of over $55 from its prior close of $18.27. The historic sell-off was attributed to a perfect storm of demand destruction from the COVID-19 pandemic, a glut of oil, and rapidly diminishing storage capacity at the Cushing, Oklahoma delivery hub, forcing traders to pay to offload oil ahead of the contract's expiration.",
            "output": {
                "sentiment_score": 1,
                "reasoning": "WTI May contract -$37.63: catastrophic. Demand collapse, storage crisis (Supply extreme imbalance). Unforeseen negative price (Exp: Very Low; Mag: Extreme). CLK20 contract failure, 1.",
                "keywords": ["WTI Negative Prices", "COVID-19 Oil Demand Shock", "Oil Storage Crisis", "CLK20 Contract Expiry", "ExtremeNegative", "MarketCollapse"]
            }
        },
        {
            "article": "WTI crude oil prices rose on Friday, November 24, 2017, with U.S. spot prices at Cushing climbing to $58.94 per barrel, marking a two-year high. The gains were attributed to the continued partial outage of the Keystone pipeline, which reduced Canadian crude flows to the U.S., and increasing market confidence that OPEC and its allies would formally agree to extend their existing production cuts at their upcoming Vienna meeting.",
            "output":{
                "sentiment_score": 75,
                "reasoning": "Keystone outage (Supply↓) & OPEC+ cut extension hopes lift oil. Mixed expectedness. WTI spot +1.83%, 2-yr high (Mag: Moderate but key). Supply tightening sentiment, 75.",
                "keywords": ["Keystone Pipeline Outage", "OPEC Production Cuts", "Oil Price Two-Year High", "SupplyConstraint", "VeryPositive"]
            }
        },
        {
            "article": "WTI crude oil prices fell sharply on Wednesday, July 11, 2018, with spot prices at Cushing dropping by nearly 5% to settle at $70.47 per barrel. The decline was attributed to several factors, including reports that Libya was set to resume oil exports from key ports sooner than expected, easing immediate supply concerns. Additionally, escalating trade tensions between the U.S. and China fueled worries about future global oil demand.",
            "output":{
                "sentiment_score":35,
                "reasoning": "Libya export resumption (Supply↑ outlook) & US-China trade fears (Demand↓ worry) drop oil. Moderately surprising supply ease. WTI spot -4.9% (Mag: Significant). Combined bearish factors, 35.",
                "keywords": ["Libya Oil Exports", "US-China Trade War", "Oil Demand Concerns", "PriceDrop", "MildlyNegative"]
            }
        }    
    ],
    # --- Gold Examples ---
    "Gold": [
        {
            "article": "Gold prices surged to a new all-time record above $1,030 per ounce in spot trading on Monday, March 17, 2008, and futures followed suit, as global financial markets reeled from the near-collapse and emergency sale of U.S. investment bank Bear Stearns to JPMorgan Chase, facilitated by the Federal Reserve. The Fed also made an emergency cut to its discount rate. The turmoil sent investors fleeing to gold as a safe haven.",
            "output": {
                "sentiment_score": 94,
                "reasoning": "Bear Stearns collapse, Fed action fueled extreme financial panic. Massive safe-haven gold demand (Demand↑↑). Highly shocking events (Exp: Very High). Gold record high (Mag: Extreme). Acute crisis, 94.",
                "keywords": ["Bear Stearns Collapse", "Global Financial Crisis 2008", "Safe Haven Demand", "Gold Record High", "Fed Emergency Action", "ExtremePositive"]
            }
        },
        {
            "article": "Gold prices experienced a historic crash on Monday, April 15, 2013, with futures plummeting by over $140 per ounce, or more than 9%, to settle around $1,361/oz. This followed a sharp drop on Friday, April 12. The sell-off was attributed to a confluence of factors including rumored large-scale selling by a major institutional holder, fears that Cyprus might be forced to sell its gold reserves, and broader market deleveraging, triggering massive stop-loss orders.",
            "output": {
                "sentiment_score": 3,
                "reasoning": "Historic gold crash. Massive selling pressure (Demand↓↓, Supply fears↑). Shocking velocity/magnitude of drop (Exp: Very High). Futures -9%+ (Mag: Extreme). Extreme panic, technical breakdown, 3.",
                "keywords": ["Gold Price Crash 2013", "Panic Selling", "StopLossCascade", "Cyprus Gold Rumors", "ExtremeNegative", "MarketMeltdown"]
            }
        },
        {
            "article": "Gold prices jumped over 2% on September 5, 2019, as weaker-than-expected U.S. manufacturing PMI data fueled concerns about a slowing U.S. economy. This disappointing data increased market expectations that the Federal Reserve would need to cut interest rates more aggressively, which tends to benefit non-yielding gold by lowering opportunity costs and potentially weakening the U.S. dollar.",
            "output": {
      "sentiment_score": 76,
      "reasoning": "Weak US PMI boosts gold investment demand. Higher Fed rate cut expectations (opportunity cost↓). Surprising data (Exp: Medium). Gold +2% (Mag: Strong). Slowdown fears aid gold; 76.",
      "keywords": ["US Manufacturing PMI Weak", "Fed Rate Cut Expectations", "GoldRally", "EconomicSlowdownFears", "VeryPositive", "SafeHaven"]
            }
        },
        {
            "article": "Gold prices edged down by about 0.8% on June 10, 2022, after U.S. consumer price index (CPI) data came in hotter than anticipated, showing inflation accelerated. This stronger-than-expected inflation reading reinforced market bets that the Federal Reserve would maintain its aggressive monetary tightening path, potentially leading to higher interest rates and a stronger dollar, both typically headwinds for gold.",
            "output":{
                "sentiment_score": 43,
                "reasoning": "Hotter US CPI bearish for gold. Reinforces hawkish Fed bets (higher rates, strong USD), reducing gold's appeal. CPI surprise (Exp: Medium). Gold -0.8% (Mag: Modest). Tightening pressure, 43.",
                "keywords": ["US CPI HotterThanExpected", "Fed Hawkish Stance Reinforced", "HigherInterestRateFears", "StrongerDollar", "MildlyNegative"]
            }
        }    
    ],
    # --- Copper Examples ---
    "Copper": [
        {
            "article": "Copper prices on the London Metal Exchange (LME) surged to an all-time nominal high above $10,800 per metric ton on Friday, March 4, 2022 (some sources cite March 7th for the peak future contract price). The rally was fueled by escalating fears of widespread supply disruptions from Russia, a key copper producer, due to sanctions imposed after its invasion of Ukraine, coupled with already critically low global stockpiles and robust demand from green energy sectors.",
            "output": {
                "sentiment_score": 93,
                "reasoning": "Ukraine war, Russia sanctions spark extreme copper supply fears (Supply↓↓). Low stocks, strong demand amplify. Unexpected disruption severity (Exp: Very High). All-time high (Mag: Extreme). Supply shock, 93.",
                "keywords": ["Ukraine War Supply Shock", "Russia Sanctions Copper", "Copper AllTime High", "Low Inventories", "ExtremePositive", "SupplyDisruptionFear"]
            }
        },
        {
            "article": "LME copper prices plunged by over 5% on Wednesday, March 18, 2020, hitting a four-year low below $4,500 per metric ton (around $2.00/lb). The sell-off intensified as governments worldwide implemented drastic lockdown measures to combat the COVID-19 pandemic, leading to factory shutdowns and a virtual halt in many sectors of the global economy, crushing expectations for industrial metals demand.",
            "output": {
                "sentiment_score": 6,
                "reasoning": "COVID demand destruction fears peak. Global lockdowns halt industry (Demand↓↓↓), crushing copper outlook. Unexpected shutdown scale (Exp: High). 4-yr low, -5% (Mag: Extreme). Demand collapse, 6.",
                "keywords": ["COVID-19 Demand Collapse", "Global Lockdown Copper", "Industrial Activity Halt", "Copper MultiYear Low", "ExtremeNegative", "RecessionFears"]
            }
        },
        {
            "article": "Copper prices rallied by more than 3.5% on October 20, 2022, after China's government announced a larger-than-expected stimulus package aimed at bolstering its economy, particularly infrastructure and construction sectors. As China is the world's largest copper consumer, this news significantly boosted demand expectations for the industrial metal.",
            "output":{
                "sentiment_score": 82,
                "reasoning": "China's large stimulus: strong copper demand boost (Demand↑↑), esp. infrastructure. Larger-than-expected package (Exp: High). Price +3.5% (Mag: Strong). Demand expectation surge, 82.",
                "keywords": ["China Economic Stimulus", "Copper Demand Boost", "InfrastructureSpending", "BullishSurprise", "VeryPositive"]
    
            }
        },
        {
            "article": "Copper prices fell around 1.8% on July 5, 2023, after manufacturing PMI data from several major economies, including the Eurozone and China, came in weaker than expected for June. These figures indicated a slowdown in global factory activity, raising concerns about near-term demand for industrial metals like copper.",
            "output":{
                "sentiment_score": 41,
                "reasoning": "Weak global manufacturing PMIs signal copper demand slowdown (Demand↓). Weaker-than-expected factory data (Exp: Medium). Price -1.8% (Mag: Modest). Demand risk from factory slowdown, 41.",
                "keywords": ["Global Manufacturing PMI Weak", "Copper Demand Concerns", "FactoryActivitySlowdown", "EconomicHeadwinds", "MildlyNegative"]
            }
        }    
    ]
}
# ---------------- [ Few-shot 예시 데이터 정의 끝 ] ----------------
# ---------------- [ Master Prompt Template 정의 ] ----------------

# 모든 지시사항을 포함하는 마스터 프롬프트 템플릿
MASTER_PROMPT_TEMPLATE = """
### Your Role & Objective ###
You are a highly specialized {commodity_name} market analysis AI. Analyze the provided news article and market context to produce a sentiment score (0-100), a concise reasoning (English, 150 chars max), and relevant keywords in a strict JSON format.

### ANALYSIS GUIDELINES ###

**I. Market Sentiment Scoring Scale (0-100):**
- 0-10 (Extreme Negative): Catastrophic events.
- 11-30 (Very Negative): Strong downward pressure.
- 31-49 (Mildly Negative): Slightly bearish.
- 50 (Neutral): In line with expectations, already priced in.
- 51-69 (Mildly Positive): Slightly bullish.
- 70-89 (Very Positive): Strong upward pressure.
- 90-100 (Extreme Positive): Paradigm-shifting positive events.

**II. Core Evaluation Factors:**
A. Supply/Demand Impact: State the anticipated shifts. Prioritize concrete data.
B. Expectedness vs. Surprise: Scores gravitate towards 50 for expected news. Surprises push scores to extremes.
C. Magnitude, Scope, & Duration: Focus on short-to-medium term impact.
D. Information Quality: Attribute higher importance to verifiable info from reputable sources.

**III. Keywords Guideline:**
Keywords MUST be specific factors impacting the commodity price (e.g., 'ethanol demand', 'export policy', 'drought conditions'). They must NOT be the commodity name itself (e.g., 'Corn') and must EXCLUDE other commodities mentioned only in passing.

### ANALYSIS TASK ###

**News Article for Your Analysis:**
{news_article_text}

Output your analysis as a single, valid JSON object ONLY, based on all guidelines and examples.
"""

# ==============================================================================
# 1. 품목명 매핑 및 변환 함수
# ==============================================================================
COMMODITY_MAP = {
    "Corn": ["corn"],
    "Wheat": ["wheat"],
    "WTI Crude Oil": ["wti", "crude oil", "oil"],
    "Gold": ["gold"],
    "Copper": ["copper"]
}

def get_simple_commodity_name(full_name_str):
    """DB에서 가져온 전체 품목명에서 핵심 품목명을 찾아 반환합니다."""
    if not full_name_str:
        return "Generic"
    
    # 소문자로 변환하여 비교
    lower_full_name = full_name_str.lower()
    
    for simple_name, keywords in COMMODITY_MAP.items():
        for keyword in keywords:
            if keyword in lower_full_name:
                return simple_name # 예: "CBOT Corn futures"에 "corn"이 있으므로 "Corn" 반환
                
    # 매핑되는 키워드가 없으면 이전 로직(마지막 단어)을 예비로 사용
    return full_name_str.split(" ")[-1]

# ==============================================================================
# 2. 프롬프트와 Few-shot 예시를 구성하는 함수
# ==============================================================================
def generate_few_shot_messages(commodity_name, news_article_text):
    """프롬프트와 Few-shot 예시를 구성하는 함수"""
    system_prompt = f"You are a highly specialized {commodity_name} market analysis AI. Your primary function is to interpret news data with nuance and objectivity, adhering strictly to the provided guidelines and examples."
    
    messages = [{"role": "system", "content": system_prompt}]

    examples = FEW_SHOT_EXAMPLES.get(commodity_name, [])
    for example in examples:
        example_prompt = MASTER_PROMPT_TEMPLATE.format(
            commodity_name=commodity_name,
            news_article_text=example['article']
        )
        messages.append({"role": "user", "content": example_prompt})
        messages.append({"role": "assistant", "content": json.dumps(example['output'])})

    actual_prompt = MASTER_PROMPT_TEMPLATE.format(
        commodity_name=commodity_name,
        news_article_text=news_article_text
    )
    messages.append({"role": "user", "content": actual_prompt})

    return messages

# ==============================================================================
# 3. GPT로 가격 연관 뉴스 필터링 함수
# ==============================================================================

def is_futures_relevant_gpt(client, commodity_name, news_title, news_content):
    prompt = f"""
Is the following news article directly relevant to the global market price or supply-demand fundamentals of {commodity_name} futures (CBOT, CME, ICE, LME, Euronext, etc.)?

Say "YES" if the article covers:
- Any change in global or regional supply, demand, production, consumption, stocks, weather (for agriculture/softs), mining/output/processing (for metals/energy), shipping/logistics, or exports/imports that could reasonably affect {commodity_name} futures or spot prices
- Government, regulatory, or international policies/actions (e.g. tariffs, quotas, sanctions, taxes, subsidies, trade agreements, environmental rules, central bank decisions) impacting supply, demand, or price
- Major geopolitical events, wars, strikes, port/plant/mine shutdowns, natural disasters, epidemics, or similar shocks
- Release of important market data, official reports, or statistics (e.g. USDA WASDE, EIA, CFTC, Crop Progress, OPEC meetings, PMI, CPI, GDP, etc.)
- Announcements from **major producers, exporters, importers, or traders** (companies, SOEs, or countries) that could shift market supply/demand balance (e.g. large production cuts/increases, export bans, capacity expansions/closures, force majeures), **only if such entities have enough market power to move prices**
- Significant financial flows, speculative activity, large fund positioning, futures/options/basis/structure changes, or market rumors influencing price
- Major technical analysis, price chart patterns, signals, or trend changes (such as moving average crossovers, head-and-shoulders, support/resistance, wave analysis, RSI, MACD, or analyst technical calls) that could influence market trading, sentiment, or trigger significant moves in {commodity_name}
- Any other news likely to affect the trading price, volatility, or global trade/sentiment for {commodity_name} or its close substitutes/related markets

Say "NO" if the article is about:
- Processed foods, finished products, recipes, consumer brands, retail trends, marketing, health/nutrition, restaurants, cafes, electronics, jewelry, fashion, or product launches
- Company news/results/sales/marketing that do **not** involve major changes to global/regional supply, demand, or price of {commodity_name} (e.g. earnings, new snack products, retail expansion, new store openings)
- General lifestyle, culture, sports, entertainment, science, technology trends, medical news, or other topics **not likely to affect market price or supply-demand** of {commodity_name}

Title: {news_title}

Body: {news_content}

Answer: YES or NO only.
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content.strip().upper()
    return answer == "YES"


# ==============================================================================
# 4. 메인 분석 함수
# ==============================================================================

def analyze_and_store_news():
    conn = None
    try:
        conn = psycopg2.connect(**db_conn_info)
        cur = conn.cursor()

        while True:
            cur.execute("SELECT id, title, content, commodity FROM raw_news WHERE analysis_status = FALSE LIMIT 5;")
            news_to_analyze = cur.fetchall()

            if not news_to_analyze:
                print("No more news to analyze. All tasks are complete.")
                break

            print(f"\n--- Found {len(news_to_analyze)} news articles to analyze. Starting batch. ---")

            for news in news_to_analyze:
                news_id, news_title, news_content, commodity_full_name = news
                commodity_simple_name = get_simple_commodity_name(commodity_full_name)
                news_text = f"Title: {news_title}\n\nBody: {news_content}"

                # ===== GPT relevance 판정 및 relevant_news 컬럼 반영 =====
                if not is_futures_relevant_gpt(client, commodity_simple_name, news_title, news_content):
                    print(f"News ID {news_id}: Not futures-relevant (GPT filter). Skipping.")
                    cur.execute("UPDATE raw_news SET analysis_status = TRUE, relevant_news = FALSE WHERE id = %s;", (news_id,))
                    conn.commit()
                    continue

                # ===== 감정분석 + relevant_news = TRUE 저장 =====
                messages = generate_few_shot_messages(commodity_simple_name, news_text)
                print(f"Analyzing news ID: {news_id} for commodity: {commodity_simple_name}")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                analysis_result = json.loads(response.choices[0].message.content)

                safe_reasoning = analysis_result.get('reasoning', '').replace('\x00', '')
                safe_keywords_json = json.dumps(analysis_result.get('keywords', [])).replace('\x00', '')

                insert_query = "INSERT INTO news_analysis_results (raw_news_id, sentiment_score, reasoning, keywords) VALUES (%s, %s, %s, %s);"
                cur.execute(insert_query, (
                    news_id,
                    analysis_result.get('sentiment_score'),
                    safe_reasoning,
                    safe_keywords_json
                ))
                # 여기서 relevant_news = TRUE로!
                update_query = "UPDATE raw_news SET analysis_status = TRUE, relevant_news = TRUE WHERE id = %s;"
                cur.execute(update_query, (news_id,))
                conn.commit()
                print(f"Successfully processed news ID: {news_id}")
                time.sleep(1)

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"An error occurred: {error}")
        if conn:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    analyze_and_store_news()