# IAM / OIDC ロール 修正依頼・手順書（管理者向け）

対象アカウント: **646977526034** / リージョン: **ap-northeast-1**

---

## 提出用サマリ（このブロックをそのままチケット／チャットへ貼り付け可）

**【依頼】IAM ロール `github-actions-s3-practice-deploy` の信頼ポリシー修正**

| 項目 | 内容 |
|---|---|
| 宛先 | （管理者） |
| 依頼者 | （記入） |
| 期限 | （記入） |
| 優先度 | 中 |
| 対象 | アカウント `646977526034` / リージョン `ap-northeast-1` |
| 対象ロール | `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy` |
| 依頼内容 | 信頼ポリシーの `token.actions.githubusercontent.com:sub` 条件を **immutable 形式**に更新（**変更は 1 箇所・所要 5 分**） |
| 理由 | GitHub Actions のデプロイが `sts:AssumeRoleWithWebIdentity` で AccessDenied |
| 代行不可の理由 | `ntcs-wan` は `NTCSDevGuardrailDenyPolicy`（`DenyTrustRelationshipTampering`）により `iam:UpdateAssumeRolePolicy` が Deny |
| 実施方法 | 下記「修正手順 → 方法A」 |
| 完了条件 | 下記「検証」のコマンドで immutable 形式の `sub` を確認 |

> 実施をお願いしたいのは **方法A のみ**です（方法B は将来の環境追加時の代替案）。

---

## 実環境の現状（確認済み）

| 項目 | 値 |
|---|---|
| OIDC プロバイダ | `arn:aws:iam::646977526034:oidc-provider/token.actions.githubusercontent.com`（存在・`ClientIDList=[sts.amazonaws.com]`） |
| デプロイロール | `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy` |
| ロールにアタッチ済み | `github-actions-s3-practice-deploy-policy`（マネージドポリシー） |
| このリポジトリが発行する `sub` | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev` |

> ⚠️ 実ロール名は **環境サフィックス無し** の `github-actions-s3-practice-deploy` です。
> `github-oidc-role.yaml` が作成する `github-actions-s3-practice-deploy-${EnvironmentName}` とは **別名**なので、
> テンプレートを新規デプロイすると **別のロールが増える** 点に注意してください（下記「方法B」参照）。

## `ntcs-wan` では修正できない理由

`ntcs-wan` にアタッチされている `NTCSDevGuardrailDenyPolicy` に次の明示 Deny があります。

- `DenyTrustRelationshipTampering`: `iam:UpdateAssumeRolePolicy` を `Resource: *` で Deny
- `DenyUserAndGroupManagement`: `iam:CreateRole` / `iam:DeleteRole` を Deny

そのため **信頼ポリシーの変更およびロール作成は管理者ユーザー等の権限で実施**してください。

## 症状

```
Error: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

## 原因

リポジトリ側で **immutable subject claim が有効**なため、OIDC トークンの `sub` は数値 ID 付きになります。

```
repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev
```

一方、デプロイロールの信頼ポリシーは旧形式のままでした。

```json
{
  "StringLike": {
    "token.actions.githubusercontent.com:sub": "repo:gyokuou0836/github_actions_for_aws:*"
  }
}
```

`StringLike` のパターンは `gyokuou0836` 直後の `/` と `github_actions_for_aws` 直後の `:`
をリテラルとして要求するため、`@5299457` / `@1416525375` が入る実トークンには **マッチしません**。

## 修正内容（変更箇所は 1 箇所だけ）

既存の 2 つの Allow 文のうち、**OIDC 用 `sub` の値だけ**を配列にして immutable 形式を追加します。
`aud` 条件・`sts:TagSession`・`ntcs-wan` 用の `sts:AssumeRole` 文は **そのまま維持**します。

```diff
       "StringLike": {
-        "token.actions.githubusercontent.com:sub": "repo:gyokuou0836/github_actions_for_aws:*"
+        "token.actions.githubusercontent.com:sub": [
+          "repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev",
+          "repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:staging",
+          "repo:gyokuou0836/github_actions_for_aws:*"
+        ]
       }
```

> `StringEquals`（`aud`）と `StringLike`（`sub`）は **条件キーが別**なので併記で問題ありません。
> 同じ条件キーに両方を書くと AND 評価になり不一致になります（末尾の「メモ」参照）。

## 修正手順

### 方法A: 既存ロールの信頼ポリシーを更新（★ご依頼内容・最速）

1. バックアップ

   ```bash
   aws iam get-role --role-name github-actions-s3-practice-deploy \
     --query 'Role.AssumeRolePolicyDocument' --output json > trust-policy.backup.json
   ```

2. `trust-policy.json` を作成（`ntcs-wan` のローカル用 AssumeRole 文も維持する）

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::646977526034:oidc-provider/token.actions.githubusercontent.com"
         },
         "Action": ["sts:AssumeRoleWithWebIdentity", "sts:TagSession"],
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
           },
           "StringLike": {
             "token.actions.githubusercontent.com:sub": [
               "repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev",
               "repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:staging",
               "repo:gyokuou0836/github_actions_for_aws:*"
             ]
           }
         }
       },
       {
         "Effect": "Allow",
         "Principal": { "AWS": "arn:aws:iam::646977526034:user/ntcs-wan" },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```

   - 1 つのロールを dev/staging で共用しているため両方の `environment:` を列挙しています。
   - 環境を問わず許可してよいなら `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:*` 1 行でも可。
   - 最後の旧形式エントリは移行用です。immutable を無効化した場合にのみ有効になります。

3. 適用

   ```bash
   aws iam update-assume-role-policy \
     --role-name github-actions-s3-practice-deploy \
     --policy-document file://trust-policy.json
   ```

   Web コンソールの場合は IAM → ロール → `github-actions-s3-practice-deploy` →
   信頼関係 → 信頼ポリシーを編集 で上記 JSON を貼り付けます。

### 方法B: CloudFormation で環境別ロールに移行する（代替案・今回は不要）

> ロールの**新規作成**も管理者ユーザーでの作業です（`ntcs-wan` は `iam:CreateRole` が Deny）。

```bash
aws cloudformation deploy --region ap-northeast-1 \
  --stack-name github-oidc-s3-practice-dev \
  --template-file iam/github-oidc-role.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides EnvironmentName=dev CreateOidcProvider=false
```

- OIDC プロバイダは既に存在するため `CreateOidcProvider=false` を指定します（テンプレート側は `Retain` 付き）。
- 作成されるロールは `github-actions-s3-practice-deploy-dev` です。
  **既存の `github-actions-s3-practice-deploy` とは別物**なので、GitHub の Environment secret
  `AWS_ROLE_ARN` を新しい `RoleArn` に更新しないとデプロイは失敗し続けます。
- 既存ロール名のまま運用を続ける場合は方法A を選んでください。

## 検証

```bash
aws iam get-role --role-name github-actions-s3-practice-deploy \
  --query 'Role.AssumeRolePolicyDocument' --output json
```

`token.actions.githubusercontent.com:sub` に immutable 形式（`@5299457` / `@1416525375` 付き）が
含まれていることを確認したうえで、GitHub Actions の `deploy` を **Re-run** します。

## 影響範囲・ロールバック

| 項目 | 内容 |
|---|---|
| 影響するロール | `github-actions-s3-practice-deploy` **のみ**（他のロール・ユーザーへの影響なし） |
| ロール／ポリシーの削除 | なし（信頼ポリシーの 1 プロパティを書き換えるのみ） |
| アタッチ済みポリシー | 変更なし（`github-actions-s3-practice-deploy-policy`） |
| 既存アクセスへの影響 | ローカル検証用の `ntcs-wan` の `sts:AssumeRole` 文は **維持**するため影響なし |
| ロールバック | 手順 1 の `trust-policy.backup.json` を `--policy-document file://trust-policy.backup.json` で再適用すれば即時復元 |
| ダウンタイム | なし（更新は即時反映） |

## 依頼者側（リポジトリ管理者）の残タスク

| # | 確認項目 | 期待値 |
|---|---|---|
| 1 | GitHub Environment `dev` の secret `AWS_ROLE_ARN` | `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy` |
| 2 | リポジトリ（または `dev` Environment）の variable `BUCKET_NAME` | `ntcs-wan-s3-practice` で始まる名前であること（ロール権限の Resource が `arn:aws:s3:::ntcs-wan-s3-practice*` のため） |
| 3 | 信頼ポリシー更新後に Actions `deploy` を **Re-run** | `configure-aws-credentials` が成功し、スタック `s3-practice-dev` が作成されること |
| 4 | 切り分け用ステップの扱い | `deploy.yml` の「Debug OIDC Token Claims」「Show Expected OIDC Subject」は復旧確認後に削除可 |

## 変更不要と確認済みの項目

以下は実環境で確認済みのため、**今回の依頼には含みません**。

| 項目 | 確認結果 |
|---|---|
| OIDC プロバイダ | `arn:aws:iam::646977526034:oidc-provider/token.actions.githubusercontent.com` が存在、`ClientIDList=[sts.amazonaws.com]` |
| ロールの権限ポリシー | `github-actions-s3-practice-deploy-policy`（v1）。CFN `stack/s3-practice-dev/*` と S3 `ntcs-wan-s3-practice*` を許可済みで、現行テンプレート `cfn/s3-bucket.yaml` の作成に必要な権限は満たしている |
| ロール名・リージョン | `github-actions-s3-practice-deploy`（環境サフィックス無し） / `ap-northeast-1`。変更不要 |
| GitHub 側 OIDC 設定 | `use_immutable_subject: true`、`sub_claim_prefix = repo:gyokuou0836@5299457/github_actions_for_aws@1416525375` |

## 信頼ポリシー `sub` の書き方メモ

| 方式 | `sub` の例 | 備考 |
|---|---|---|
| immutable（推奨） | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev` | Settings → Actions → OIDC で immutable subject が有効な場合 |
| 旧形式 | `repo:gyokuou0836/github_actions_for_aws:environment:dev` | immutable を無効化した場合のみ |

- 同じ条件キーに `StringEquals` と `StringLike` を併記すると **AND 評価**になり一致しません。
  どちらか一方に統一してください（移行期は `StringLike` の配列にまとめる）。
- `sub` に含まれる数値 ID は「リポジトリ固有の不変 ID」です。オーナー名やリポジトリ名を変更しても
  この値は変わりません（`GitHubOwnerId` / `GitHubRepositoryId` の既定値と一致）。

## 参考: 今後ロールを新規作成する場合のひな形

環境を追加する際にロールを新規作成するときも、`sub` は必ず **immutable 形式**（`@数値ID` 付き）で
指定してください。本リポジトリの `iam/github-oidc-role.yaml` がそのまま正しい形です。

| 設定項目 | 値 |
|---|---|
| 信頼されたエンティティ | `oidc-provider/token.actions.githubusercontent.com` |
| `aud` | `sts.amazonaws.com`（`StringEquals`） |
| `sub` | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:<env>`（`StringLike`） |
| Action | `sts:AssumeRoleWithWebIdentity`（＋ `sts:TagSession`） |
| 権限 | スタック `s3-practice-<env>` への CFN 操作と、`ntcs-wan-s3-practice*` への S3 操作 |
| ロール名の注意 | テンプレートは `github-actions-s3-practice-deploy-<env>` を作成するため、既存の `github-actions-s3-practice-deploy` とは**別ロール**になる。作成後は GitHub の `AWS_ROLE_ARN` 更新が必要（上記「方法B」参照） |
