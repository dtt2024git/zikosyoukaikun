import discord
import gspread
import datetime
import asyncio
import re
import os # ファイル操作のためにインポート
from typing import Optional, Dict

# ボットのインテントを設定
# メッセージの内容とメンバー情報を読み取るために必要です。
# Discord Developer PortalでMESSAGE CONTENT INTENTとSERVER MEMBERS INTENTをONにしてください。
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ボットオブジェクトを初期化
bot = discord.Client(intents=intents)

# --- 設定項目 ---

# -- Discord関係 --

# あなたのボットのトークンをここに貼り付けてください
YOUR_BOT_TOKEN = ''
# ロールを付与したいチャンネルのIDをここに貼り付けてください
TARGET_CHANNEL_ID = 
# 付与したいロールのIDをここに貼り付けてください
ROLE_TO_GIVE_ID = 

# 管理者向けログを送信するチャンネルのIDをここに貼り付けてください
ADMIN_LOG_CHANNEL_ID = 

# Discord規約違反の年齢（13歳未満）が検出された際の絵文字 (管理者ログでのみ使用)
AGE_VIOLATION_EMOJI_FOR_ADMIN_LOG = '🚫'

# ロール付与成功時のリアクション絵文字（元のメッセージに表示）
SUCCESS_REACTION_EMOJI = ''

# ロール付与失敗時または条件不適合時のリアクション絵文字（元のメッセージに表示）
FAILURE_REACTION_EMOJI = ''

# 年齢規約違反時に管理者ログチャンネルでメンションを有効にするか (True/False)
ENABLE_ADMIN_MENTION = False # Trueにするとメンションが飛びます

# 管理者ログチャンネルでメンションする文字列 (ロールIDまたはユーザーID)
# 例: '<@&ロールID>' または '<@ユーザーID>'
ADMIN_MENTION_STRING = '<@&123456789012345678>' # ← メンションしたいロールIDまたはユーザーIDに設定！

# --- 💡 新規追加: 管理者向けコマンド設定 ---
# ボット管理者のユーザーID
ADMIN_USER_ID = 
# ログとシートをクリアするための特定のキーワード
RESET_COMMAND_KEYWORD = 'リセット'

# -- Google Sheets API --

# JSONキーファイルのパス (ボットのPythonコードと同じディレクトリに配置)
SERVICE_ACCOUNT_FILE = 'service_account.json'
# 作成したGoogleスプレッドシートの名前
SPREADSHEET_NAME = ''
# データを書き込むシートの名前
WORKSHEET_NAME = ''

# 鯖落ち対策設定
# ログファイルの名前
LAST_PROCESSED_FILE = 'last_processed_timestamp.txt'
# 初回起動時に最終処理タイムスタンプがない場合のデフォルト処理件数
DEFAULT_INITIAL_PROCESS_LIMIT = 1000

# --- 設定項目ここまで ---

# gspreadクライアントを初期化
try:
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    print("Google Sheets API クライアントを初期化しました。")
except Exception as e:
    print(f"Google Sheets API クライアントの初期化に失敗しました: {e}")
    print(f"サービスアカウントファイル '{SERVICE_ACCOUNT_FILE}' が存在するか、権限が正しいか確認してください。")
    gc = None

# 管理者ログチャンネルオブジェクトをグローバル変数として定義
admin_log_channel: Optional[discord.TextChannel] = None
spreadsheet: Optional[gspread.Spreadsheet] = None


def get_last_processed_timestamp() -> Optional[datetime.datetime]:
    """
    最後に処理されたメッセージのタイムスタンプをファイルから読み込む。
    ファイルが存在しない場合や内容が不正な場合はNoneを返す。
    """
    try:
        with open(LAST_PROCESSED_FILE, 'r') as f:
            timestamp_str = f.read().strip()
            if timestamp_str:
                # タイムゾーン情報がない場合はUTCとして扱う
                dt = datetime.datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                return dt
    except FileNotFoundError:
        return None
    except ValueError: # ファイル内容が不正な場合
        print(f"警告: '{LAST_PROCESSED_FILE}' の内容が不正です。ファイルをリセットします。")
        return None
    return None


def update_last_processed_timestamp(timestamp: datetime.datetime):
    """
    最後に処理されたメッセージのタイムスタンプをファイルに書き込む。
    タイムスタンプはUTC形式で保存される。
    """
    # タイムゾーン情報がある場合はUTCに変換して保存
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(datetime.timezone.utc)
    with open(LAST_PROCESSED_FILE, 'w') as f:
        f.write(timestamp.isoformat())
    print(f"最終処理タイムスタンプを更新しました: {timestamp}")


def _reset_log_file():
    """
    ログファイル `LAST_PROCESSED_FILE` を削除またはクリアする。
    """
    try:
        if os.path.exists(LAST_PROCESSED_FILE):
            os.remove(LAST_PROCESSED_FILE)
            print(f"ログファイル '{LAST_PROCESSED_FILE}' を削除しました。")
    except Exception as e:
        print(f"ログファイルの削除中にエラーが発生しました: {e}")


async def _clear_google_sheets(channel: discord.TextChannel):
    """
    指定されたスプレッドシートのワークシートをクリアする。
    """
    global spreadsheet
    # スプレッドシートへの接続が確立されていなければ、再度初期化を試みる
    if not spreadsheet and gc:
        try:
            spreadsheet = gc.open(SPREADSHEET_NAME)
            print("スプレッドシートへの接続を再試行しました。")
        except gspread.exceptions.SpreadsheetNotFound:
            await channel.send(f"エラー: スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
            print(f"エラー: スプレッドシートが見つからず、クリアできませんでした。")
            return
        except Exception as e:
            await channel.send(f"エラー: スプレッドシートへの接続に失敗しました: {e}")
            print(f"スプレッドシートへの接続エラー: {e}")
            return

    if not spreadsheet:
        await channel.send("エラー: Googleスプレッドシートへの接続が確立されていません。")
        print("スプレッドシートが未接続のため、クリアできませんでした。")
        return

    try:
        # ログシートをクリア
        log_worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        log_worksheet.clear()
        print(f"スプレッドシートの '{WORKSHEET_NAME}' シートをクリアしました。")

        # 念のため、クリア後のヘッダー行を追加
        log_worksheet.append_row([
            'タイムスタンプ(UTC)', 'ユーザーID', 'ユーザー名',
            '名前があるか', '一言があるか', '13歳未満の可能性', 'メッセージリンク'
        ])
        await channel.send("✅ Googleスプレッドシートのログをクリアしました。")

    except gspread.exceptions.WorksheetNotFound as e:
        await channel.send(f"エラー: シート '{e.args[0]}' が見つかりません。")
        print(f"エラー: シートが見つからず、クリアできませんでした: {e}")
    except Exception as e:
        await channel.send(f"エラー: スプレッドシートのクリア中に予期せぬエラーが発生しました: {e}")
        print(f"スプレッドシートのクリア中にエラーが発生しました: {e}")


async def _process_message_logic(message: discord.Message):
    """
    個々のメッセージに対する処理ロジックを実行する。
    メッセージの内容チェック、ロールの付与、スプレッドシートへのログ記録、リアクションの追加を行う。
    """
    global spreadsheet
    # ボット自身のメッセージには反応しない
    if message.author == bot.user:
        return

    # 指定されたチャンネルからのメッセージか確認
    if message.channel.id == TARGET_CHANNEL_ID:
        # メッセージの内容を小文字に変換してチェック（大文字・小文字を区別しないため）
        message_content_lower = message.content.lower()

        # --- メッセージ内容のキーワードチェック ---
        # 名前関連キーワードの検出
        name_keyword_found = any(keyword in message_content_lower for keyword in ['名前', 'ニックネーム', 'ハンドルネーム', 'ハンネ' , 'ペンネ' , 'hn' , 'ネーム' , 'ｈｎ'])
        # 「一言」キーワードの検出
        hitokoto_keyword_found = any(keyword in message_content_lower for keyword in ['一言', 'ひと言', 'ひとこと', '一こと' , '１こと' , '１言' , '1こと' , '1言'])

        # --- 年齢違反の検出 ---
        age_violation_detected = False

        # メッセージを改行で分割し、各行をチェック
        lines = message.content.lower().split('\n')

        # 新しいルールに合わせた正規表現とキーワードリスト
        # SR1: 0-12の数字（半角/全角）
        num_0_12_regex = r'\b(0|1|2|3|4|5|6|7|8|9|10|11|12|０|１|２|３|４|５|６|７|８|９|１０|１１|１２)\b'
        # SR1の年齢単位と括弧
        age_unit_and_parentheses_regex = r'(歳|才|さい|\(|\))'

        # SR2: 小学生関連キーワード
        elementary_keywords = ['小学生', '小学', '小1', '小２', '小3', '小４', '小5', '小６', '小１', '小２', '小３', '小４', '小５', '小６']

        # SR3: 中学1年生関連キーワード
        middle_school_first_year_keywords = ['中一', '中1', '中学1年生', '中１', '中学1年', '中学１年', '中学１年生']
        # SR3: 13の数字（半角/全角/漢字）
        num_13_variations_regex = r'\b(13|１３|十三)\b'

        for line in lines:
            # この行がSR1, SR2, SR3のいずれかの条件に単体で適合したか
            line_meets_any_sr_condition = False
            # この行に「年齢」という言葉があるか
            is_age_word_present_on_line = '年齢' in line

            # --- Rule 1 (SR1): 0~12の数字と歳、才、さい、（、）、(、)がいずれか1つ以上同じ行にある場合 ---
            # 例: 「私は10歳です」「私は(5才)」
            if re.search(num_0_12_regex, line) and re.search(age_unit_and_parentheses_regex, line):
                line_meets_any_sr_condition = True
                print(f"年齢検出（SR1）: '{line}'")

            # --- Rule 2 (SR2): 小学生、小学...のいずれかがある場合 ---
            # 例: 「私は小学生です」「小学一年生になりました」
            if any(keyword in line for keyword in elementary_keywords):
                line_meets_any_sr_condition = True
                print(f"年齢検出（SR2）: '{line}'")

            # --- Rule 3 (SR3): 中一...のいずれかがある AND 13(半角/全角/漢字)がある場合 ---
            # かつ、それらの言葉と同じ行に１３、13、十三のいずれかと同じ行に歳、才、さいがあるばあい
            # 修正: '才', 'さい', '(', ')' ではなく '歳', '才', 'さい' のいずれか
            # ルールの解釈: (中一系キーワードがある) AND (13系キーワードがある) AND (歳/才/さいがある) が同じ行にある場合。
            found_ms_keyword_on_line = any(keyword in line for keyword in middle_school_first_year_keywords)
            found_13_variation_on_line = bool(re.search(num_13_variations_regex, line))
            found_age_unit_on_line_for_sr3 = bool(re.search(r'(歳|才|さい)', line)) # SR3の年齢単位は「歳」「才」「さい」のみ

            if found_ms_keyword_on_line and found_13_variation_on_line and found_age_unit_on_line_for_sr3:
                line_meets_any_sr_condition = True
                print(f"年齢検出（SR3）: '{line}'")

            # --- 最終判断: いずれかのSRルールがその行で満たされ、かつ「年齢」という言葉がその行にある場合 ---
            if line_meets_any_sr_condition and is_age_word_present_on_line:
                age_violation_detected = True
                print(f"最終年齢違反検出: 行 '{line}' がルールに適合し、かつ「年齢」が含まれる。")
                break # 違反が見つかったら行ループを抜ける

        # ロール付与が最終的に成功したかどうかのフラグ
        role_granted_successfully = False

        # --- スプレッドシートへのメッセージログ書き込み処理 (指定チャンネルの全メッセージが対象) ---
        if gc:
            try:
                # ログを書き込む前にスプレッドシートへの接続を確認
                if not spreadsheet:
                    spreadsheet = gc.open(SPREADSHEET_NAME)

                worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

                # ヘッダー行が存在しない場合、追加する
                if not worksheet.row_values(1):
                    worksheet.append_row([
                        'タイムスタンプ(UTC)', 'ユーザーID', 'ユーザー名',
                        '名前があるか', '一言があるか', '13歳未満の可能性', 'メッセージリンク'
                    ])
                    print("スプレッドシートにヘッダー行を追加しました。")

                # ユーザー情報をリストとして準備
                user_data = [
                    datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(message.author.id),
                    message.author.display_name,
                    'True' if name_keyword_found else 'False',
                    'True' if hitokoto_keyword_found else 'False',
                    'True' if age_violation_detected else 'False',
                    message.jump_url
                ]
                worksheet.append_row(user_data)
                print(f'スプレッドシートにログ情報を書き込みました: {message.author.display_name} (メッセージID: {message.id})')

            except gspread.exceptions.SpreadsheetNotFound:
                print(f'エラー: スプレッドシート "{SPREADSHEET_NAME}" が見つかりません。名前が正しいか、サービスアカウントと共有されているか確認してください。')
            except gspread.exceptions.WorksheetNotFound:
                print(f'エラー: ワークシート "{WORKSHEET_NAME}" がスプレッドシート "{SPREADSHEET_NAME}" 内に見つかりません。')
            except Exception as e:
                print(f'スプレッドシートへの書き込み中にエラーが発生しました: {e}')
        else:
            print("Google Sheets API クライアントが初期化されていないため、スプレッドシートへの書き込みはスキップされました。")
        # --- スプレッドシートへのメッセージログ書き込み処理ここまで ---


        # --- ロール付与のロジック ---
        guild = message.guild
        member = None
        if guild:
            member = guild.get_member(message.author.id)

        # ロール付与の前提条件 (名前と一言のキーワードが存在すること)
        if name_keyword_found and hitokoto_keyword_found:
            if member:
                try:
                    role_to_give = discord.utils.get(guild.roles, id=ROLE_TO_GIVE_ID)
                    if role_to_give:
                        # 名前と一言の条件を満たせばロールを付与する (年齢違反の有無に関わらず)
                        if role_to_give not in member.roles:
                            await member.add_roles(role_to_give)
                            print(f'ユーザー {member.display_name} にロール {role_to_give.name} を付与しました。')
                        else:
                            print(f'ユーザー {member.display_name} は既にロール {role_to_give.name} を持っています。')
                        role_granted_successfully = True # ロール付与成功

                    else:
                        print(f'エラー: ロールID {ROLE_TO_GIVE_ID} のロールが見つかりません。')
                        role_granted_successfully = False
                except discord.Forbidden:
                    print(f'エラー: ロール付与の権限がありません。ボットにロール管理の権限を与え、BOTのロールが付与したいロールより上にあるか確認してください。')
                    role_granted_successfully = False
                except discord.HTTPException as e:
                    print(f'Discord API エラーが発生しました: {e}')
                    role_granted_successfully = False
                except Exception as e:
                    print(f'予期せぬエラーが発生しました: {e}')
                    role_granted_successfully = False
            else:
                print(f'エラー: メンバー情報が見つかりません。')
                role_granted_successfully = False
        else:
            # 名前と一言の条件を満たさない場合
            print(f'ユーザー {message.author.display_name} のメッセージはロール付与条件（名前と一言）を満たしませんでした。')
            role_granted_successfully = False # ロールは付与されない


        # --- 管理者ログチャンネルへのメッセージ送信と元のメッセージへのリアクション ---
        try:
            # 管理者ログチャンネルには年齢違反が検出された場合のみ送信
            # ここではage_violation_detectedはSR1, SR2, SR3に関わらず「問題あり判定」を意味する
            if age_violation_detected and admin_log_channel:
                log_message = f"{AGE_VIOLATION_EMOJI_FOR_ADMIN_LOG} **年齢規約違反検出**\n" \
                              f"ユーザー: {message.author.mention} (`{message.author.display_name}` / `{message.author.id}`)\n" \
                              f"メッセージ: {message.jump_url}\n" \
                              f"検出内容: メッセージにDiscord規約違反の年齢情報が含まれています。\n"

                # ロール付与条件（名前と一言）を満たしたかどうかに応じてメッセージを追記
                if name_keyword_found and hitokoto_keyword_found:
                    # 年齢違反検出済みだがロール付与成功（自己紹介完了）の場合
                    role_name = "不明なロール"
                    if guild and discord.utils.get(guild.roles, id=ROLE_TO_GIVE_ID):
                        role_name = discord.utils.get(guild.roles, id=ROLE_TO_GIVE_ID).name
                    log_message += f"→ 自己紹介条件を満たしたため、ロール `{role_name}` が付与されました（**規約違反の可能性あり**）。"
                else:
                    # 自己紹介条件を満たさないためロール付与せず
                    log_message += f"→ ロール付与は行われませんでした（自己紹介条件を満たしていません）。"

                if ENABLE_ADMIN_MENTION and ADMIN_MENTION_STRING:
                    log_message = f"{ADMIN_MENTION_STRING} {log_message}" # メンションを追加

                await admin_log_channel.send(log_message)
                print(f"管理者ログチャンネルに年齢規約違反メッセージを送信しました。")

            # 元のメッセージへのリアクション (年齢違反の有無に関わらず⭕️/❌を付ける)
            if role_granted_successfully: # ロール付与成功
                await message.add_reaction(SUCCESS_REACTION_EMOJI)
                print(f'メッセージに「{SUCCESS_REACTION_EMOJI}」リアクションを追加しました。')
            else: # ロール付与失敗 (条件不適合)
                await message.add_reaction(FAILURE_REACTION_EMOJI)
                print(f'メッセージに「{FAILURE_REACTION_EMOJI}」リアクションを追加しました。')

        except discord.Forbidden:
            print(f'エラー: Discordへの操作権限がありません (メッセージ送信/リアクション追加)。ボットの権限を確認してください。')
        except discord.HTTPException as e:
            print(f'Discord APIエラーが発生しました (メッセージ送信/リアクション追加): {e}')
        except Exception as e:
            print(f'予期せぬエラーが発生しました (メッセージ送信/リアクション追加): {e}')


async def _remove_bot_reactions_from_channel(channel: discord.TextChannel):
    """
    指定されたチャンネル内のすべてのメッセージから、ボットが追加したリアクションを削除する。
    これは主に、ログファイルが存在しない初回起動時などに、以前のリアクションをクリーンアップするために使用される。
    """
    print(f"チャンネル '{channel.name}' のメッセージからボットのリアクションを削除中...")
    removed_count = 0
    message_count = 0
    async for message in channel.history(limit=None): # チャンネルの全メッセージを遡る
        message_count += 1
        try:
            # メッセージに付いている各リアクションをチェック
            for reaction in message.reactions:
                # そのリアクションをボットが追加したかどうかを確認
                # asyncio.gatherを使用して非同期にユーザーをリスト化
                users = [user async for user in reaction.users()]
                if bot.user in users:
                    # ボットが追加したリアクションであれば削除
                    await message.remove_reaction(reaction.emoji, bot.user)
                    removed_count += 1
                    print(f"メッセージ {message.id} からボットのリアクション '{reaction.emoji}' を削除しました。")
                    # Discord APIのレートリミットを考慮して、適度に待機
                    await asyncio.sleep(0.5)

        except discord.Forbidden:
            print(f"エラー: メッセージ {message.id} からリアクションを削除する権限がありません。")
        except discord.HTTPException as e:
            print(f"メッセージ {message.id} からリアクション削除中にHTTPエラーが発生しました: {e}")
        except Exception as e:
            print(f"メッセージ {message.id} からリアクション削除中に予期せぬエラーが発生しました: {e}")

    print(f"チャンネル '{channel.name}' のメッセージからボットのリアクション削除が完了しました。\n"
          f"処理したメッセージ数: {message_count}\n"
          f"削除したリアクション数: {removed_count}")


async def _process_messages_in_channel(
    channel: discord.TextChannel,
    after_dt: Optional[datetime.datetime] = None,
    limit: Optional[int] = None
) -> Optional[datetime.datetime]:
    """
    指定されたチャンネルのメッセージ履歴を処理し、最後に処理されたメッセージのタイムスタンプを返す。
    これは主に、ボットがオフラインだった間のメッセージをキャッチアップするために使用される。
    """
    messages_to_process = []

    # メッセージ取得の条件に応じて履歴を遡る
    if after_dt:
        # 指定日時以降のメッセージを古い順に取得
        print(f"チャンネル '{channel.name}' で {after_dt} (UTC) 以降のメッセージを取得中...")
        if after_dt.tzinfo is None:
            after_dt = after_dt.replace(tzinfo=datetime.timezone.utc)
        async for msg in channel.history(limit=None, after=after_dt, oldest_first=True):
            messages_to_process.append(msg)
    elif limit is not None:
        # 最新の指定件数のメッセージを取得し、古い順に並べ替え
        print(f"チャンネル '{channel.name}' で最新の {limit} 件のメッセージを取得中...")
        temp_messages = []
        async for msg in channel.history(limit=limit):
            temp_messages.append(msg)
        messages_to_process = temp_messages[::-1] # リストを逆順にして古い順にする
    else:
        # after_dtまたはlimitが指定されていない場合は処理をスキップ
        print("メッセージ取得の条件が指定されていません。")
        return None

    if not messages_to_process:
        print("処理する新しいメッセージはありませんでした。")
        return None

    latest_message_timestamp = None
    processed_count = 0
    skipped_count = 0

    for message in messages_to_process:
        # ボット自身のメッセージやシステムメッセージはスキップ
        if message.author == bot.user or message.type != discord.MessageType.default:
            skipped_count += 1
            continue

        await _process_message_logic(message)
        processed_count += 1
        # Discordのメッセージの作成時刻はUTCなので、そのまま記録
        latest_message_timestamp = message.created_at

        # Discord APIのレートリミットを考慮して、適度に待機
        await asyncio.sleep(0.5)

    print(f"過去メッセージの処理が完了しました。\n"
          f"処理されたメッセージ数: {processed_count}\n"
          f"スキップされたメッセージ数 (ボットやシステムメッセージなど): {skipped_count}")

    return latest_message_timestamp


@bot.event
async def on_ready():
    """ボットがDiscordに正常にログインした際に実行される。"""
    print(f'ボット {bot.user} でログインしました。')

    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not target_channel:
        print(f"エラー: 設定されたターゲットチャンネルID {TARGET_CHANNEL_ID} が見つかりません。")
        return

    # Google Sheets APIの初期化
    global gc, spreadsheet
    try:
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
        spreadsheet = gc.open(SPREADSHEET_NAME)
        print("Google Sheets API クライアントとスプレッドシートを初期化しました。")
    except Exception as e:
        print(f"Google Sheets API の初期化に失敗しました: {e}")
        print(f"サービスアカウントファイル '{SERVICE_ACCOUNT_FILE}' が存在するか、権限が正しいか、"
              f"スプレッドシート '{SPREADSHEET_NAME}' が存在するか、サービスアカウントと共有されているか確認してください。")
        # 失敗した場合は以降のシート関連処理をスキップ
        spreadsheet = None

    # グローバル変数に管理者ログチャンネルを代入
    global admin_log_channel
    admin_log_channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if not admin_log_channel:
        print(f"警告: 管理者ログチャンネルID {ADMIN_LOG_CHANNEL_ID} が見つかりません。管理者への通知は行われません。")


    last_processed_dt = get_last_processed_timestamp()

    if last_processed_dt:
        # 最終処理時刻が記録されている場合、その時刻以降のメッセージを処理
        print(f"最終処理時刻 {last_processed_dt.isoformat()} 以降のメッセージを自動で処理します。")
        latest_processed_dt = await _process_messages_in_channel(target_channel, after_dt=last_processed_dt)
        if latest_processed_dt and latest_processed_dt > last_processed_dt:
            update_last_processed_timestamp(latest_processed_dt)
        else:
            print("処理する新しいメッセージはありませんでした。")
    else:
        # 最終処理時刻の記録がない場合（初回起動など）、過去のリアクションをクリーンアップし、最新のメッセージを処理
        print(f"最終処理時刻の記録が見つかりません。チャンネルのリアクションをクリーンアップします。")
        await _remove_bot_reactions_from_channel(target_channel) # ログがないのでリアクションを全て削除

        print(f"最新の {DEFAULT_INITIAL_PROCESS_LIMIT} 件のメッセージを処理します。")
        latest_processed_dt = await _process_messages_in_channel(target_channel, limit=DEFAULT_INITIAL_PROCESS_LIMIT)
        if latest_processed_dt:
            update_last_processed_timestamp(latest_processed_dt)


@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視する
    if message.author == bot.user:
        return
    # Botへのメンションかどうかを判定
    if bot.user.mentioned_in(message):
        if message.author.id == ADMIN_USER_ID and RESET_COMMAND_KEYWORD in message.content:
            await message.channel.send("🚧 ログファイルとスプレッドシートをクリアしています...")
            # ログファイルをリセット
            _reset_log_file()
            # スプレッドシートのデータをクリア
            await _clear_google_sheets(message.channel)
            await message.channel.send("✅ クリアが完了しました。ボットを再起動します。")
            # ボットをシャットダウン
            await bot.close()
            return # これ以上処理しない
        else:
            # 逆ギレのセリフリスト
            outbursts = [
                f"{message.author.mention}！うるせえ！なんか用かよ！",
                f"おい、{message.author.mention}か！話しかけてくんな！",
                f"{message.author.mention}、人のことメンションしてんじゃねーよ！",
                f"あ？{message.author.mention}か。もう知らねー！"
            ]
            import random
            await message.channel.send(random.choice(outbursts))
    else:
        # リアルタイムで受信したメッセージのタイムスタンプを常に最新として更新
        # message.created_at はUTCタイムゾーン情報を持つdatetimeオブジェクトです。
        update_last_processed_timestamp(message.created_at)
        # メッセージ処理ロジックを実行
        await _process_message_logic(message)

# ボットを実行
bot.run(YOUR_BOT_TOKEN)
