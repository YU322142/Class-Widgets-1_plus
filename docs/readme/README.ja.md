<div align="right">
<a href="/README.md">简体中文</a> | <a href="/docs/readme/README.en_US.md">English</a> | 日本語
</div>

<p align="center">
  <img width="16%" align="center" src="../../img/Logo.png" alt="logo">
</p>
<h1 align="center">Class Widgets 1_plus</h1>
<p align="center">Class Widgets 1 の軽量改変版（Fork）</p>

<div align="center">

> ⚠️ このプロジェクトは上流プロジェクトを元にした非公式の改変版であり、上流公式チームには所属していません。<br>
> ⚠️ この文書は人工知能翻訳を使用しています
</div>

## 特徴

- **Loongson LoongArch プロセッサ環境でトランスレーション実行が可能で、上流プロジェクトに近い互換性を維持**
- **より小さいフローティングウィンドウ**で、画面占有を削減
- Python 製の**プラグイン**システムとプラグインプラザ（最新ビルド参照）
- 今日の授業予定を**ウィジェット形式**で表示
- [授業開始/終了通知](https://www.yuque.com/rinlit/class-widgets_help/fv2ou1i1ngap0hrl) と予鈴に対応し、TTS 通知をサポート
- 高度なカスタマイズが可能なテーマシステム
- シンプルで直感的な[時間割エディター](https://www.yuque.com/rinlit/class-widgets_help/oozelh8r56tmw0xb)
- 複数の時間割ファイル保存、および Class Widgets 間でのインポート/エクスポートに対応
- [**共通時間割交換フォーマット**（CSES）](https://github.com/SmartTeachCN/CSES) に対応し、形式変換が可能
- 振替・授業変更への迅速な[対応方法](https://www.yuque.com/rinlit/class-widgets_help/gc4epffu7g5bf9os)を提供
- 「天気」「カスタムカウントダウン」など実用的なウィジェットを提供
- [「カスタム」](https://www.yuque.com/rinlit/class-widgets_help/qyly70ht1ogge1pi)で Class Widgets を個別最適化
- ライト/ダークテーマ対応、システム設定による自動切替にも対応;<br>...

## 上流との差分（主な変更点）

- 小型フローティングウィンドウのレイアウトを追加/調整
- ......

## 変更部分のスクリーンショット

#### 小型フローティングウィンドウ

![scrshot_0](../../img/screenshot_2.png)

![scrshot_0](../../img/screenshot_3.png)

## インストールと使い方

> [!TIP]
> 上流の [Class Widgets 公式ドキュメント](https://www.yuque.com/rinlit/class-widgets_help/gs3gsbms1iivgibm) を参照できます。

Releases のアーカイブをダウンロードして解凍し、`ClassWidgets.exe` を実行してください。  
設定の変更や終了はトレイメニューから行えます。

> [!IMPORTANT]
> バイナリ（exe/zip）を配布する場合は、対応する完全なソースコードを取得できるようにしてください（下記ライセンス参照）。

## ライセンス（License）

本プロジェクトは **GNU General Public License v3.0 (GPL-3.0)** の下で公開されています。  
詳細は [LICENSE](./LICENSE) を参照してください。

本プロジェクトは上流プロジェクトの改変版（Fork）です：

- Upstream: [Class-Widgets/Class-Widgets](https://github.com/Class-Widgets/Class-Widgets)
- 上流著作権：Copyright © 2025 RinLit.
- 本 Fork 改変部分の著作権：Copyright © 2026 YU322142.

### GPL 準拠について（バイナリ配布時）

実行ファイルやパッケージ（exe/zip）を配布する場合、  
対応する完全なソースコードを同時に提供するか、明確かつ有効な入手方法（同一リポジトリの該当 tag/release など）を提示してください。

### 非公式 Fork 声明

本プロジェクトは**非公式** Fork であり、上流公式プロジェクトに**所属せず**、**代表せず**、**公式な承認を受けていません**（明示がある場合を除く）。

### 名称・素材について

プロジェクト名、ロゴ、および一部の画像/アイコン素材の権利は、原作者または各権利者に帰属する場合があります。  
再配布時は、関連ライセンス範囲を必ず確認してください。

## 謝辞

### 上流プロジェクト

- [Class-Widgets/Class-Widgets](https://github.com/Class-Widgets/Class-Widgets)

長期にわたり開発・保守を続けている上流メンテナおよび全コントリビュータに感謝します。

### サードパーティライブラリ・フレームワーク

- [PyQt5](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- [Loguru](https://github.com/Delgan/loguru)
- [Requests](https://github.com/psf/requests)

### 素材

- [SF Symbols](https://developer.apple.com/jp/sf-symbols/)（一部アイコンを改変）
- [QWeather Icons](https://icons.qweather.com/en/)（一部アイコンを改変）
- [Segoe Fluent Icons](https://learn.microsoft.com/ja-jp/windows/apps/design/style/segoe-fluent-icons-font)（一部アイコンを改変）
- [HarmonyOS Sans](https://developer.huawei.com/consumer/en/design/resource/)

## コミュニティとフィードバック

- この Fork のコミュニティ：現在なし
- 上流コミュニティ（参考）：
  - [Discussions](https://github.com/orgs/Class-Widgets/discussions)
  - [QQグループ](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=yHXKCAjOxlpTpJ4mNdXm0mxOneYUinRs&authKey=sd3%2F06iGdOZUjkXXPBeIzGnFDIeYwmdwuM8dhk25fi%2B1CUL32MkeN2EEfjdo2pzE&noverify=0&group_code=169200380)
  - [Discord](https://discord.gg/EFF4PpqpqZ)

---

これは新人としての練習プロジェクトです。ご意見・ご提案を歓迎します！
