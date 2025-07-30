# discord-self-intro-role-bot

## 概要
このDiscordボットは、特定のチャンネルに投稿された自己紹介メッセージを監視し、メッセージの内容に基づいてロールを付与または管理します。また、Googleスプレッドシートにメッセージログを記録し、特定の年齢規約違反の可能性がある投稿を管理者チャンネルに通知する機能も備えています。

## 機能
- 自己紹介チャンネルでのロール自動付与（名前と一言のキーワード検出）
- 自己紹介メッセージのGoogleスプレッドシートへのログ記録
- Discord規約に違反する可能性のある年齢情報の検出と管理者への通知（設定可能）
- ユーザーの投稿チャンネルへのリアクションによる処理結果の表示

## セットアップ方法

### 1. Discord Botの作成と設定
1.  [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、新しいアプリケーションを作成します。
2.  作成したアプリケーションの「Bot」タブに移動し、「Add Bot」をクリックしてボットを追加します。
3.  「Privileged Gateway Intents」セクションで **MESSAGE CONTENT INTENT** と **SERVER MEMBERS INTENT** を**ON**にしてください。
4.  「Bot」タブでボットのトークンをコピーし、後でコードに貼り付けます。**このトークンは誰にも教えないでください。**
5.  「OAuth2」タブの「URL Generator」で、`bot` スコープと、必要な権限（例: `Manage Roles`, `Read Message History`, `Send Messages`, `Add Reactions`）を選択し、生成されたURLであなたのサーバーにボットを招待します。

### 2. Google Sheets APIの設定
1.  [Google Cloud Console](https://console.cloud.com/) にアクセスします。
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

## AI生成について
このボットのコードは、GoogleのAIモデルによって生成されました。

## ライセンス
このプロジェクトは [Apache-2.0 License](https://www.apache.org/licenses/LICENSE-2.0) の下で公開されています。
