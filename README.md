# github_actions_for_aws
GitHub Actions 練習用

## 構成
- `cfn/s3-bucket.yaml` : S3バケットのCloudFormationテンプレート
- `scripts/deploy.py` : boto3によるスタック作成/更新
- `.github/workflows/deploy.yml` : 環境別デプロイ
- `iam/github-oidc-role.yaml` : OIDCプロバイダ + 環境別デプロイロール（管理者が実行）

## 環境
| GitHub Environment | トリガー | スタック名 |
|---|---|---|
| dev | `deploy_dev` へのMerge | s3-practice-dev |
| staging | `deploy_stg` へのMerge | s3-practice-staging |
| prod | 手動実行のみ（将来 `deploy_prod` 追加） | s3-practice-prod |

手動実行: Actions → deploy → **Run workflow** → environment を選択。
PR時は `validate` ジョブのみ（テンプレート検証）。

## 事前準備
`ntcs-wan` にはIAM権限が無いため、ロールは管理者権限を持つ別ユーザーが作成する（Webコンソール手順でも可。信頼ポリシーの `sub` は `repo:gyokuou0836/github_actions_for_aws:environment:<環境名>`）。

1. 環境ごとにロール作成（OIDCプロバイダは最初の1回のみ作成。2回目以降は `CreateOidcProvider=false`）
   ```
   aws cloudformation deploy --region ap-northeast-1 \
     --stack-name github-oidc-s3-practice-dev \
     --template-file iam/github-oidc-role.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides EnvironmentName=dev
   ```
   出力 `RoleArn` を控える。
2. GitHub: Settings → Environments で `dev` / `staging` / `prod` を作成
   - Environment secrets: `AWS_ROLE_ARN`（その環境のRoleArn）
   - Environment variables: `BUCKET_NAME`（`ntcs-wan-s3-practice` で始める）
   - Deployment branches: dev=`deploy_dev`、staging=`deploy_stg`、prod=承認者(Required reviewers)を設定推奨
   ※PR時の検証は `cfn-lint` を使用するため、Repository Secretの登録は不要です。

## 流れ
`feature/wangyu` で編集 → `deploy_dev` へPR → Merge → Actionsがdevスタックを更新
