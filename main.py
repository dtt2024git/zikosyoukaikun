import discord
import gspread
import datetime
import asyncio
import re
from typing import Optional

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
ADMIN_LOG_CHANNEL_ID = 123456789012345678 # ← このIDを設定してください！

# Discord規約違反の年齢（13歳未満）が検出された際の絵文字 (管理者ログでのみ使用)
# この設定は年齢検出ロジックが削除されたため、機能しなくなります。
AGE_VIOLATION_EMOJI_FOR_ADMIN_LOG = '🚫'

# ロール付与成功時のリアクション絵文字（元のメッセージに表示）
SUCCESS_REACTION_EMOJI = '⭕' 

# ロール付与失敗時または条件不適合時のリアクション絵文字（元のメッセージに表示）
FAILURE_REACTION_EMOJI = '❌' 

# 年齢規約違反時に管理者ログチャンネルでメンションを有効にするか (True/False)
# この設定は年齢検出ロジックが削除されたため、機能しなくなります。
ENABLE_ADMIN_MENTION = True 

# 管理者ログチャンネルでメンションする文字列 (ロールIDまたはユーザーID)
# 例: '<@&ロールID>' または '<@ユーザーID>'
# この設定は年齢検出ロジックが削除されたため、機能しなくなります。
ADMIN_MENTION_STRING = '<@&123456789012345678>'


# -- Google Sheets API --

# JSONキーファイルのパス (ボットのPythonコードと同じディレクトリに配置)
SERVICE_ACCOUNT_FILE = 'service_account.json'
# 作成したGoogleスプレッドシートの名前
SPREADSHEET_NAME = '幻の曲を探そう鯖のログ'
# データを書き込むシートの名前
WORKSHEET_NAME = '自己紹介'

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


async def _process_message_logic(message: discord.Message):
    """
    個々のメッセージに対する処理ロジックを実行する。
    メッセージの内容チェック、ロールの付与、スプレッドシートへのログ記録、リアクションの追加を行う。
    """
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
        hitokoto_keyword_found = '一言' in message_content_lower

        # --- 年齢違反の検出 ---
        # 年齢検出ロジックは削除されました。
        age_violation_detected = False 
        
        # ロール付与が最終的に成功したかどうかのフラグ
        role_granted_successfully = False

        # --- スプレッドシートへのメッセージログ書き込み処理 (指定チャンネルの全メッセージが対象) ---
        if gc:
            try:
                spreadsheet = gc.open(SPREADSHEET_NAME)
                worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

                # ヘッダー行が存在しない場合、追加する
                if not worksheet.row_values(1):
                    worksheet.append_row([
                        'タイムスタンプ(UTC)', 'ユーザーID', 'ユーザー名',
                        '名前があるか', '一言があるか', 'メッセージリンク' # '13歳未満の可能性'を削除
                    ])
                    print("スプレッドシートにヘッダー行を追加しました。")

                # ユーザー情報をリストとして準備
                user_data = [
                    datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                    str(message.author.id),                                
                    message.author.display_name,                           
                    'True' if name_keyword_found else 'False',             
                    'True' if hitokoto_keyword_found else 'False',         
                    # 'True' if age_violation_detected else 'False', # 年齢検出の項目を削除       
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
                        # 名前と一言の条件を満たせばロールを付与する
                        if role_to_give not in member.roles:
                            await member.add_roles(role_to_give)
                            print(f'ユーザー {member.display_name} にロール {role_to_give.name} を付与しました。')
                        else:
                            print(f'ユーザー {member.display_name} は既にロール {role_to_give.name} を持っています。')
                        role_granted_successfully = True # ロール付与成功
                        
                        # 年齢規約違反が検出されてもロールは剥奪しないロジックは削除されました
                        
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
        # 年齢違反検出ロジックが削除されたため、管理者ログチャンネルへのメッセージ送信は行われません。
        try:
            # 元のメッセージへのリアクション
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
                async for user in reaction.users():
                    if user == bot.user:
                        # ボットが追加したリアクションであれば削除
                        await message.remove_reaction(reaction.emoji, bot.user)
                        removed_count += 1
                        print(f"メッセージ {message.id} からボットのリアクション '{reaction.emoji}' を削除しました。")
                        break # このリアクションは処理したので次のリアクションへ
            
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
    """新しいメッセージが送信された際に実行される。"""
    # ボット自身のメッセージは処理しない
    if message.author == bot.user:
        return

    # リアルタイムで受信したメッセージのタイムスタンプを常に最新として更新
    # message.created_at はUTCタイムゾーン情報を持つdatetimeオブジェクトです。
    update_last_processed_timestamp(message.created_at)
    # メッセージ処理ロジックを実行
    await _process_message_logic(message)

# ボットを実行
bot.run(YOUR_BOT_TOKEN)
