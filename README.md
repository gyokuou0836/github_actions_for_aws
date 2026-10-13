# github_actions_for_aws
GitHub Actions 練習用

## 構成
- `cfn/s3-bucket.yaml` : S3バケットのCloudFormationテンプレート
- `scripts/deploy.py` : boto3によるスタック作成/更新
- `.github/workflows/deploy-dev.yml` : `deploy_dev` へのMergeでデプロイ

## 事前準備
1. AWSにGitHub OIDCプロバイダと、CloudFormation/S3権限を持つIAMロールを作成（信頼ポリシーはこのリポジトリ限定）
2. GitHub Secrets: `AWS_ROLE_ARN` / Variables: `BUCKET_NAME`（グローバル一意）

## 流れ
`feature/wangyu` で編集 → `deploy_dev` へPR → Merge → Actionsがスタックを更新
