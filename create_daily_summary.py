import os
import psycopg2
import openai
import json
from dotenv import load_dotenv
from datetime import date
import httpx


# .env 파일에서 API 키 불러오기
load_dotenv()

custom_http_client = httpx.Client(verify=False)

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=custom_http_client
)

# 데이터베이스 연결 정보
db_conn_info = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

def generate_summary_for_day(cur, conn, target_date, target_commodity):
    """지정된 날짜와 품목에 대한 일일 종합 리포트를 생성하고 DB에 저장합니다."""
    
    print(f"\n--- Starting daily summary for {target_commodity} on {target_date} ---")
    
    # 1. 해당 날짜, 품목의 모든 개별 분석 결과 가져오기
    fetch_query = """
    SELECT n.sentiment_score, n.reasoning, n.keywords
    FROM raw_news r
    JOIN news_analysis_results n ON r.id = n.raw_news_id
    WHERE r.commodity = %s AND r.published_time::date = %s AND r.analysis_status = TRUE;
    """
    cur.execute(fetch_query, (target_commodity, target_date))
    results = cur.fetchall()

    if not results:
        print(f"No analyzed news found for {target_commodity} on {target_date}.")
        return

    analyzed_news_count = len(results)
    print(f"Found {analyzed_news_count} analyzed articles.")

    # 2. 가중 평균 점수 계산
    total_weighted_score = 0
    total_weight = 0
    all_reasonings = []
    all_keywords = {}

    for row in results:
        score, reasoning, keywords = row
        if score is None: continue

        # 가중치 계산: |점수 - 50| + 1
        weight = abs(score - 50) + 1
        total_weighted_score += score * weight
        total_weight += weight
        
        all_reasonings.append(reasoning)
        # 키워드 빈도수 계산
        for keyword in keywords:
            all_keywords[keyword] = all_keywords.get(keyword, 0) + 1
    
    # 최종 가중 평균 점수
    daily_sentiment_score = total_weighted_score / total_weight if total_weight > 0 else 50.0

    # 3. GPT를 이용해 Reasoning 및 Keywords 요약
    print("Summarizing daily reasoning and keywords with OpenAI...")
    
    summarization_prompt = f"""
    You are a Head Market Analyst. Below are individual analysis reports from your team for {target_commodity} on {target_date}.
    Your task is to synthesize them into a single, concise daily summary report in JSON format.

    Individual Reasonings:
    {json.dumps(all_reasonings, indent=2)}

    All Individual Keywords (with frequency):
    {json.dumps(all_keywords, indent=2)}

    ---
    Please generate a final summary based on the provided data.
    - daily_reasoning: A single, coherent English sentence (max 150 chars) summarizing the most dominant market driver of the day.
    - daily_keywords: A list of the 5 most representative keywords for the day's market theme, selected from the provided list.

    Output only the final JSON object.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a Head Market Analyst responsible for creating concise daily summaries."},
            {"role": "user", "content": summarization_prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    summary_result = json.loads(response.choices[0].message.content)
    daily_reasoning = summary_result.get('daily_reasoning')
    daily_keywords = summary_result.get('daily_keywords')

    # 4. daily_market_summary 테이블에 결과 저장 (UPSERT: 없으면 INSERT, 있으면 UPDATE)
    upsert_query = """
    INSERT INTO daily_market_summary (date, commodity, daily_sentiment_score, daily_reasoning, daily_keywords, analyzed_news_count)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (date, commodity) DO UPDATE SET
        daily_sentiment_score = EXCLUDED.daily_sentiment_score,
        daily_reasoning = EXCLUDED.daily_reasoning,
        daily_keywords = EXCLUDED.daily_keywords,
        analyzed_news_count = EXCLUDED.analyzed_news_count;
    """
    cur.execute(upsert_query, (
        target_date,
        target_commodity,
        daily_sentiment_score,
        daily_reasoning,
        json.dumps(daily_keywords),
        analyzed_news_count
    ))
    conn.commit()
    print(f"Successfully created/updated daily summary for {target_commodity} on {target_date}.")


def main():
    """스크립트의 메인 실행 함수"""
    conn = None
    try:
        conn = psycopg2.connect(**db_conn_info)
        cur = conn.cursor()

        # 분석은 완료됐지만, 아직 일일 요약이 생성되지 않은 모든 (날짜, 품목) 조합을 찾습니다.
        find_jobs_query = """
        (SELECT DISTINCT published_time::date AS date, commodity
         FROM raw_news
         WHERE analysis_status = TRUE)
        EXCEPT
        (SELECT date, commodity
         FROM daily_market_summary);
        """
        cur.execute(find_jobs_query)
        jobs_to_do = cur.fetchall()

        if not jobs_to_do:
            print("No new daily summaries to generate. All summaries are up-to-date.")
            return

        print(f"Found {len(jobs_to_do)} new daily summaries to generate.")

        # 찾아낸 각 조합에 대해 일일 요약 함수를 실행합니다.
        for job in jobs_to_do:
            target_date, target_commodity = job
            if target_date and target_commodity:
                generate_summary_for_day(cur, conn, target_date, target_commodity)

        cur.close()

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"An error occurred: {error}")
        if conn:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
            print("\nAll tasks finished. Database connection closed.")


if __name__ == '__main__':
    main()