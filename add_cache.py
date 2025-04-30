from sqlalchemy import create_engine
import pandas as pd
from MyCache import SemanticCache
import json
from sqlalchemy import text


def update_cache():
    engine = create_engine(
        'mysql+pymysql://')
    pd.set_option('display.max_colwidth', None)

    semantic_cache = SemanticCache()    # 初始化缓存

    # 筛选出符合条件的问题加入缓存
    query = '''
        SELECT DISTINCT
            a.question,
            a.`sql`,
            a.echarts_code
        FROM
            cm_report_error_feedback AS a
        JOIN
            cm_report_error_feedback AS b
        ON
            REPLACE(a.`sql`," ", "") = REPLACE(b.`sql`," ", "") AND
            a.question = b.question AND
            a.if_result_true = 1 AND
            b.if_result_true = 1 AND
            a.echarts_code IS NOT NULL AND 
            a.if_result_cache = 0 AND 
            b.if_result_cache = 0 
        WHERE
          SUBSTR(a.`time`, 1, 10) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AND 
          a.question IN (SELECT question FROM cm_report_error_feedback GROUP BY cm_report_error_feedback.question HAVING SUM(if_result_cache) = 0) 
    '''
    df = pd.read_sql(query, engine)

    for index, row in df.iterrows():
        semantic_cache.set(
            row['question'],
            row['sql'],
            json.loads(row['echarts_code'])
        )

    # 将已经加入缓存的问题的缓存情况更新为1(if_result_cache = 1代表已经加入缓存)
    df = df.drop_duplicates(subset=['question'])
    for index, row in df.iterrows():
        with engine.connect() as connection1:
            update_1 = text(f'UPDATE cm_report_error_feedback SET if_result_cache = 1 WHERE question = "{row[0]}"')
            connection1.execute(update_1)
            connection1.commit()

    with engine.connect() as connection2:
        update_2 = text('''
            UPDATE cm_report_error_feedback
            SET if_result_cache = 1
            WHERE question IN (
                SELECT DISTINCT question FROM (
                    SELECT question
                    FROM cm_report_error_feedback
                    GROUP BY question
                    HAVING SUM(if_result_cache) > 0
                ) AS temp
            );
    ''')
        connection2.execute(update_2)
        connection2.commit()

    # 删去冗余的问题
    with engine.connect() as connection3:
        update_3 = text('''
            DELETE FROM cm_report_error_feedback
            WHERE question IN (
                SELECT DISTINCT question FROM (
                    SELECT question
                    FROM cm_report_error_feedback
                    WHERE if_result_cache = 1
                ) AS temp 
            ) AND
            echarts_code IS NULL
        ''')
        connection3.execute(update_3)
        connection3.commit()


if __name__ == "__main__":
    update_cache()  # 保留原有手动执行的能力
