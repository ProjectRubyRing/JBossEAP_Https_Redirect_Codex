# JBoss EAP 8.1／ALB HTTPS リダイレクト対応資料

最初に `JBossEAP81_ALB_HTTPS_Redirect_Report.xlsx` の「01_結論」を読むと、構成に合う対応を選べます。全体の文章版は `JBossEAP81_ALB_HTTPS_Redirect_Report.md` です。

- `08_稼働中のCLI`：起動中のコンテナでの確認・設定。
- `09_起動前の実装`／`10_恒久化`：再作成後も設定を維持する方法。
- `11_独自フィルタ`：アプリ側で URL を直接指定する場合の対応。
- `13_検証手順`／`14_適用と切り戻し`：実動作の確認と元への戻し方。
- `18_出典`：30件の公式資料・一次情報へのリンク。

`scripts/` の例は、実際のターゲットグループの転送方式、リスナー名、構成ファイル名に合わせて使用します。`default-server`、`default`、`example.net`、`/opt/server` 等は実環境の値を確認して置き換えます。スクリプトを順番にすべて実行する構成ではありません。必要なファイルの選び方は17章に記載しています。

`assets/https_flow.png` は通信の模式図、`assets/previews/` は実際のセルデータを Meiryo UI で描画した確認用画像です。プレビューは Excel 画面のスクリーンショットではありません。

`validation_results.txt`、`artifact_validation.json`、`preview_validation.json` 等に、実施した検証と未実施の確認を記録しています。EAP／ALBの実環境変更・実動作試験は行っていません。

資料を再生成する場合は、WindowsのMeiryo UI、Python 3、Pillow、XlsxWriter、openpyxlを使います。本環境では既存インストールを利用しました。

```powershell
python -B .\tools\build_report.py
python -B .\tools\validate_artifacts.py
python -B .\tools\render_preview.py
```

`tools/inspect_excel.py` は、利用者のWindows環境でExcel本体を使った読み取り・印刷確認を行う任意の検証実装です。本作業環境では COM の起動が失敗しました。実行にはExcel、pywin32、PyMuPDFが必要です。通常の資料再生成には使いません。
