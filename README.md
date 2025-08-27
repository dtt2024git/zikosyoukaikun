# 自己紹介君

## 概要
本ソースコードはDiscordServer「[つくば科学万博　冨田勲さんの幻の曲を探す会](https://discord.gg/kZFtnEs4HD)」で提供させていただいている自己紹介君のソースコードです

ただし、各ユーザーの名前等、トークンやIDなどが含まれる部分は削除加工されています

仕様・使い方は記述してあるため、他のユーザーが利用しても問題はありませんが、不具合等のさまざまな**責任は一切負いません**

ソースコードを利用してbotをセットアップするには下の[セットアップ方法](https://github.com/dtt2024git/zikosyoukaikun/blob/main/README.md#%E3%82%BB%E3%83%83%E3%83%88%E3%82%A2%E3%83%83%E3%83%97%E6%96%B9%E6%B3%95)をご覧ください

また、本ソースコードはGoogleのAIモデル Geminiを使用して作成しました

(管理者へ　復元は[こちら](https://github.com/dtt2024git/zikosyoukaikun/blob/main/README.md#%E7%AE%A1%E7%90%86%E8%80%85%E5%90%91%E3%81%91%E5%BE%A9%E5%85%83%E6%96%B9%E6%B3%95)へ

## セットアップ方法

### 1. Discord Botの作成と設定
1.  [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、新しいアプリケーションを作成します。
2.  作成したアプリケーションの「Bot」タブに移動し、「Add Bot」をクリックしてボットを追加します。
3.  「Privileged Gateway Intents」セクションで **MESSAGE CONTENT INTENT** と **SERVER MEMBERS INTENT** を**ON**にしてください。
4.  「Bot」タブでボットのトークンをコピーし、後でコードに貼り付けます。**このトークンは誰にも教えないでください。**
5.  「OAuth2」タブの「URL Generator」で、`bot` スコープと、必要な権限（例: `Manage Roles`, `Read Message History`, `Send Messages`, `Add Reactions`）を選択し、生成されたURLであなたのサーバーにボットを招待します。

### 2. Google Sheets APIの設定
1.  [Google Cloud Console](https://console.cloud.google.com/) にアクセスします。
2.  新しいプロジェクトを作成するか、既存のプロジェクトを選択します。
3.  「APIとサービス」>「ライブラリ」に移動し、「Google Drive API」と「Google Sheets API」を検索して**有効化**します。
4.  「APIとサービス」>「認証情報」に移動し、「認証情報を作成」>「サービスアカウント」を選択します。
5.  サービスアカウント名を入力し、ロールとして「プロジェクト」>「閲覧者」などを付与します（必要に応じてより厳密なロールを設定してください）。
6.  サービスアカウント作成後、そのサービスアカウントのキーをJSON形式でダウンロードします。ダウンロードしたJSONファイルをボットのPythonスクリプトと同じディレクトリに配置し、ファイル名を`service_account.json`に変更してください。
7.  Googleスプレッドシートを作成し、ボットがアクセスできるように、作成したサービスアカウントのメールアドレス（JSONファイル内に記載されています）をスプレッドシートの共有設定に追加し、「編集者」権限を付与してください。

### 3. Python環境の準備
1.  Python 3.8以上がインストールされていることを確認します。
2.  以下のコマンドで必要なライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

### 4. ボットの設定と実行
1.  `main.py` (ボットのPythonスクリプト) を開き、以下の設定変数をあなたの環境に合わせて更新します。
    -   `YOUR_BOT_TOKEN`: Discord Developer Portalでコピーしたボットのトークン。
    -   `TARGET_CHANNEL_ID`: 自己紹介メッセージを監視するチャンネルのID。
    -   `ROLE_TO_GIVE_ID`: 自己紹介が完了したユーザーに付与するロールのID。
    -   `ADMIN_LOG_CHANNEL_ID`: 管理者向けログを送信するチャンネルのID。
    -   `SERVICE_ACCOUNT_FILE`: `service_account.json`のファイル名（通常は変更不要）。
    -   `SPREADSHEET_NAME`: Googleスプレッドシートの名前。
    -   `WORKSHEET_NAME`: スプレッドシート内のワークシートの名前。
    -   `ENABLE_ADMIN_MENTION`: 年齢規約違反時に管理者チャンネルでメンションを有効にするか（`True`/`False`）。
    -   `ADMIN_MENTION_STRING`: 管理者チャンネルでメンションする文字列（例: `<@&ロールID>` または `<@ユーザーID>`）。

2.  ボットを実行します。
    ```bash
    python main.py
    ```
これで完成

## 管理者向け　復元方法
!!復元時は`last_processed_timestamp.txt`とスプレッドシートの内容を削除

[Discord Developer Portal](https://discord.com/developers/applications)へアクセス

当該BOTを選択->BOT->ResetTokenでトークンをリセット＆コピー

＞一時的に保存（ローカル）

[Google Cloud Console](https://console.cloud.google.com/)へアクセス

当該プロジェクトに切り替える

APIとサービス->認証情報->サービスアカウント内の本BOT用アカウント->鍵->キーを追加->新しい鍵を追加

でキーを追加してjson形式でダウンロード

以前までのキーは無効に（削除）

jsonファイルを`service_account.json`に名前を変える

そこからサーバーのコンソールで、

```bash
sudo apt install python3 python3-venv python3-pip git screen -y
screen -r
git clone https://github.com/dtt2024git/zikosyoukaikun
cd zikosyoukaikun
```

jsonファイルをサーバーへscpかsftpでアップロード（公開鍵認証で）

なにかしら（nano等）でmain.pyを修正

・トークン修正

・ローカルのフルコードコピー

そこから

```bash
python -m venv ziko-venv
source ziko-venv/bin/activate
pip install -r requirements.txt
python main.py
```
これで動くはず

## ライセンス
このプロジェクトは [Apache-2.0 License](https://www.apache.org/licenses/LICENSE-2.0) の下で公開されています。
