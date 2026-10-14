# github_actions_for_aws
GitHub Actions 練習用

## 構成
- `cfn/s3-bucket.yaml` : S3バケットのCloudFormationテンプレート
- `scripts/deploy.py` : boto3によるスタック作成/更新
- `.github/workflows/deploy.yml` : 環境別デプロイ
- `iam/github-oidc-role.yaml` : OIDCプロバイダ + 環境別デプロイロール（管理者が実行）
- `iam/README.md` : 管理者への修正依頼書（実環境のロール情報・信頼ポリシー修正手順・影響範囲）

## 環境
| GitHub Environment | トリガー | スタック名 |
|---|---|---|
| dev | `deploy_dev` へのMerge | s3-practice-dev |
| staging | `deploy_stg` へのMerge | s3-practice-staging |
| prod | 手動実行のみ（将来 `deploy_prod` 追加） | s3-practice-prod |

手動実行: Actions → deploy → **Run workflow** → environment を選択。
PR時は `validate` ジョブのみ（テンプレート検証）。

## 事前準備
`ntcs-wan` にはIAM権限が無いため、ロールは管理者権限を持つ別ユーザーが作成する（Webコンソール手順でも可）。信頼ポリシーの `sub` は GitHub OIDC の immutable ID 形式（`repo:<owner>@<owner-id>/<repository>@<repository-id>:environment:<環境名>`）に合わせる。現在の既定値では dev は `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev`。異なるリポジトリを使う場合はテンプレートの owner/repository 名と ID を変更する。

1. 環境ごとにロール作成（OIDCプロバイダは最初の1回のみ作成。2回目以降は `CreateOidcProvider=false`）
   ```
   aws cloudformation deploy --region ap-northeast-1 \
     --stack-name github-oidc-s3-practice-dev \
     --template-file iam/github-oidc-role.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides EnvironmentName=dev
   ```
   出力 `RoleArn` を控える。
   既存のロールが旧形式の `sub`（`repo:<owner>/<repository>:environment:<環境名>`）を信頼している場合、このリポジトリのように GitHub が immutable ID 形式の `sub` を発行していることを確認してから、このテンプレートでスタックを更新する。immutable subject に移行していない既存リポジトリは引き続き旧形式を発行するため、先に GitHub 側で移行するか、移行中は両形式を信頼してから旧形式を削除する。
2. GitHub: Settings → Environments で `dev` / `staging` / `prod` を作成
   - Environment secrets: `AWS_ROLE_ARN`（その環境のRoleArn）
   - Environment variables: `BUCKET_NAME`（`ntcs-wan-s3-practice` で始める）
   - Deployment branches: dev=`deploy_dev`、staging=`deploy_stg`、prod=承認者(Required reviewers)を設定推奨
   ※PR時の検証は `cfn-lint` を使用するため、Repository Secretの登録は不要です。

## 流れ
`feature/wangyu` で編集 → `deploy_dev` へPR → Merge → Actionsがdevスタックを更新

## トラブルシューティング

### `Not authorized to perform sts:AssumeRoleWithWebIdentity`

このリポジトリは GitHub OIDC の **immutable subject**（数値ID付き）を発行します。

```
repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev
```

ロールの信頼ポリシーが旧形式（`repo:gyokuou0836/github_actions_for_aws:*` など）のままだと
`sub` が一致せず AssumeRole に失敗します。実環境のロール ARN・現在の信頼ポリシー・更新手順は
[`iam/README.md`](iam/README.md) を参照してください。

> デプロイロールは `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy`（環境サフィックス無し）。
> `ntcs-wan` は `NTCSDevGuardrailDenyPolicy` の `DenyTrustRelationshipTampering` により
> `iam:UpdateAssumeRolePolicy` が Deny されているため、更新は管理者ユーザーで実施してください。
>
> ワークフローの「Debug OIDC Token Claims」「Show Expected OIDC Subject」ステップで、
> 実際に発行された `sub` と信頼ポリシーが必要とする `sub` をログで比較できます
> （切り分けが完了したら削除して構いません）。
