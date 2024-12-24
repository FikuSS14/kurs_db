import json


def create_db(cur):
    """Создает таблицы в базе данных."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS words(
            id SERIAL PRIMARY KEY,
            word VARCHAR(30) NOT NULL,
            id_user VARCHAR(30) NOT NULL
            );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS translates(
            id SERIAL PRIMARY KEY,
            word VARCHAR(30) NOT NULL,
            id_eng INTEGER REFERENCES words(id)
            );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS deleted_words(
            id SERIAL PRIMARY KEY,
            id_eng INTEGER REFERENCES words(id),
            id_transl INTEGER REFERENCES translates(id),
            id_user VARCHAR(30) NOT NULL
            );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS word_rating(
            id SERIAL PRIMARY KEY,
            id_user VARCHAR(30),
            id_eng INTEGER REFERENCES words(id),
            id_transl INTEGER REFERENCES translates(id),
            rating INTEGER NOT NULL
            );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_statistic(
            id SERIAL PRIMARY KEY,
            id_user VARCHAR(30) NOT NULL,
            stat INTEGER NOT NULL
            );
        """
    )


def new_user(cur, cid):
    """Добавляет нового пользователя и его слова в базу данных."""
    with open(r"test_data.json", encoding="utf-8") as file:
        words = json.load(file)
        for word in words:
            cur.execute(
                """
                INSERT INTO words (word, id_user)
                VALUES(%s, %s)
                RETURNING id;
                """,
                (word, str(cid)),
            )
            eng_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO translates (word, id_eng)
                VALUES(%s, %s)
                RETURNING id;
                """,
                (words[word], eng_id),
            )
            transl_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO word_rating (id_user, id_eng, id_transl, rating)
                VALUES(%s, %s, %s, %s);
                """,
                (str(cid), eng_id, transl_id, 0),
            )

            cur.execute(
                """
                INSERT INTO user_statistic (id_user, stat)
                VALUES(%s, %s)
                """,
                (str(cid), 0),
            )


def search_words(cur, cid):
    """Ищет слова пользователя в базе данных."""
    cur.execute(
        """
        SELECT t.word, w.word
        FROM translates t
        JOIN words w ON w.id = t.id_eng
        WHERE w.id_user = %s;
        """,
        (str(cid),),
    )
    all_words = cur.fetchall()

    deleted_words = []
    try:
        cur.execute(
            """
            SELECT w.word, t.word
            FROM deleted_words dw
            JOIN words w ON w.id = dw.id_eng
            JOIN translates t ON t.id_eng = w.id
            WHERE w.id_user = %s;
            """,
            (str(cid),),
        )
        deleted_words += cur.fetchall()
    except:
        pass

    result = []
    en_list = []
    transl_list = []
    if len(deleted_words) > 0:
        en_list += [i[0] for i in deleted_words]
        transl_list += [i[1] for i in deleted_words]
    for i in all_words:
        if i[1] not in en_list and i[0] not in transl_list:
            result.append(i)

    return result


def true_answer(cur, cid, en_word, translate):
    """Обновляет рейтинг слова и статистику пользователя при верном ответе."""
    cur.execute(
        """
        SELECT t.id, w.id
        FROM translates t
        JOIN words w ON w.id = t.id_eng
        WHERE w.word = %s
        AND t.word = %s
        AND w.id_user = %s;
        """,
        (en_word, translate, str(cid)),
    )

    ans = cur.fetchone()

    if ans is None:
        raise ValueError("Не удалось найти слово по указанным критериям")

    transl_id = ans[0]
    en_id = ans[1]

    cur.execute(
        """
        UPDATE word_rating
        SET rating = rating + 1
        WHERE id_user = %s AND id_eng = %s AND id_transl = %s;
        """,
        (str(cid), en_id, transl_id),
    )

    try:
        cur.execute(
            """
            SELECT rating
            FROM word_rating
            WHERE id_user = %s AND id_eng = %s AND id_transl = %s;
            """,
            (str(cid), en_id, transl_id),
        )
        ans = cur.fetchone()

        if ans is None:
            raise ValueError("Не удалось получить рейтинг слова")

        current_rating = ans[0]

        if int(current_rating) == 20:
            del_word(cur, cid, en_word, translate)

        cur.execute(
            """
            UPDATE user_statistic
            SET stat = stat + 1
            WHERE id_user = %s;
            """,
            (str(cid),),
        )
    except Exception as e:
        print(f"Ошибка при обновлении рейтинга: {e}")


def adding_word(cur, cid, en_word, translate):
    """Добавляет новое слово и его перевод в базу данных."""
    cur.execute(
        """
        INSERT INTO words (word, id_user)
        VALUES(%s, %s)
        RETURNING id;
        """,
        (en_word, str(cid)),
    )
    eng_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO translates (word, id_eng)
        VALUES(%s, %s)
        RETURNING id;
        """,
        (translate, eng_id),
    )
    transl_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO word_rating (id_eng, id_transl, rating)
        VALUES(%s, %s, %s);
        """,
        (eng_id, transl_id, 0),
    )


def del_word(cur, cid, en_word, translate):
    """Удаляет слово из базы данных и помещает его в список удаляемых слов."""
    cur.execute(
        """
        SELECT t.id, w.id
        FROM translates t
        JOIN words w ON w.id = t.id_eng
        WHERE w.word = %s
        AND t.word = %s
        AND w.id_user = %s;
        """,
        (en_word, translate, str(cid)),
    )

    ans = cur.fetchone()

    if ans is None:
        raise ValueError(
            f"Слово {en_word} или его перевод {translate} не найдено для пользователя {cid}"
        )

    transl_id = ans[0]
    en_id = ans[1]

    cur.execute(
        """
        INSERT INTO deleted_words (id_eng, id_transl, id_user)
        VALUES(%s, %s, %s);
        """,
        (en_id, transl_id, str(cid)),
    )
