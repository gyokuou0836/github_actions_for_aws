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

1. 環境ごとにロール作成（OIDCプロバイダはアカウントに1つ。本アカウントには既に `token.actions.githubusercontent.com` が存在するため `CreateOidcProvider=false` を指定）
   ```
   aws cloudformation deploy --region ap-northeast-1 \
     --stack-name github-oidc-s3-practice-dev \
     --template-file iam/github-oidc-role.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides EnvironmentName=dev CreateOidcProvider=false
   ```
   出力 `RoleArn` を控える。
   既存のロールが旧形式の `sub`（`repo:<owner>/<repository>:environment:<環境名>`）を信頼している場合、このリポジトリのように GitHub が immutable ID 形式の `sub` を発行していることを確認してから、このテンプレートでスタックを更新する。immutable subject に移行していない既存リポジトリは引き続き旧形式を発行するため、先に GitHub 側で移行するか、移行中は両形式を信頼してから旧形式を削除する。
2. GitHub: Settings → Environments で `dev` / `staging` / `prod` を作成
   - Environment secrets: `AWS_ROLE_ARN`（その環境のRoleArn）
   - Environment variables: `BUCKET_NAME`（`ntcs-wan-s3-practice` で始める）
   - Deployment branches: dev=`deploy_dev`、staging=`deploy_stg`、prod=承認者(Required reviewers)を設定推奨
   ※PR時の検証は `cfn-lint` を使用するため、Repository Secretの登録は不要です。

## 事前準備チェックリスト（PR → デプロイ実行）

デプロイを実行する前に次を確認します。`ntcs-wan` は AWS 側（IAM）の設定を変更できないため、
**信頼ポリシーの修正は管理者の作業完了が前提**です。

### AWS 側（管理者が実施）

- [x] ロール `github-actions-s3-practice-deploy` の信頼ポリシーが immutable 形式（`@5299457` / `@1416525375` 付き）
      — **2026-10-14 更新済み・実測確認済み**。未実施のまま実行すると `configure-aws-credentials` で
      `Not authorized to perform sts:AssumeRoleWithWebIdentity` になります
- [x] 確認コマンド: `aws iam get-role --role-name github-actions-s3-practice-deploy --query 'Role.AssumeRolePolicyDocument'`

### GitHub 側（リポジトリ設定）

- [x] Environment `dev` が存在する（`staging` / `prod` を使う場合も同様に作成）
      — 実行ログの `sub` が `environment:dev` になっていることで確認済み
- [x] Environment `dev` の **Secret** `AWS_ROLE_ARN` = `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy`
      （**環境サフィックス無し**。`...-dev` を設定すると存在しないロールを指します）
      — ロール引受けに成功しスタックが作成されたことで確認済み
- [x] Environment `dev` の **Variable** `BUCKET_NAME`（ワークフローは `vars.BUCKET_NAME` を参照。Secret ではない）
      — `ntcs-wan-s3-practice` で始め、S3 全体で一意にする（ロール権限が `arn:aws:s3:::ntcs-wan-s3-practice*` のため）
      実値: `ntcs-wan-s3-practice-wangyu-526034`
- [ ] Environment `dev` の Deployment branches に `deploy_dev` を許可（ブランチ制限を掛けている場合）
- [ ] Environment `dev` に Required reviewers を設定している場合は、実行後に承認する
- [ ] Settings → Actions → General で Actions が有効（`id-token: write` はワークフロー内で宣言済み）

### 実行の挙動（つまずきやすい点）

| 操作 | 走るジョブ | 理由 |
|---|---|---|
| PR 作成（`feature/wangyu` → `deploy_dev`） | **なし** | `pull_request` の `paths` は `cfn/**` のみ。ドキュメントだけの PR にはチェックが付かない |
| PR をマージ（`deploy_dev` へ push） | `deploy`（environment=`dev`） | `push` の `paths` に `.github/workflows/deploy.yml` が含まれ、マージ差分で `deploy.yml` が変わるため |
| 「Re-run」ボタン | — | PR では実行が無いため、マージ後まで使えない |
| 手動実行（Run workflow） | `deploy` | Actions → deploy → Run workflow → environment で `dev` を選択。ブランチは `deploy_dev` を選ぶ（Deployment branches の許可対象にするため） |

### ロール権限との整合（確認済み）

| 項目 | 内容 |
|---|---|
| 付与済み権限 | CFN `stack/s3-practice-dev/*` の `CreateStack` / `UpdateStack` / `DescribeStacks` / `DescribeStackEvents` / `GetTemplate`、`ValidateTemplate`、S3 `ntcs-wan-s3-practice*` の Create/Put/Get/List |
| `scripts/deploy.py` が使う操作 | `DescribeStacks` → `CreateStack` / `UpdateStack` → `DescribeStacks`（waiter）: すべて付与済み |
| ⚠️ 注意 | ポリシーのスタック対象は **`s3-practice-dev` のみ**。`workflow_dispatch` で `staging`/`prod` を選ぶとスタック操作の権限が無く失敗します。さらに方法Aの信頼ポリシーは `dev`/`staging` のみを許可するため、`prod` はロール引受けの時点でも失敗します（使う場合は `prod` の immutable `sub` とスタック権限の両方を管理者に追加依頼） |

## デプロイ結果（実測）

2026-10-14 の初回デプロイは**成功**しました（信頼ポリシー更新後に Re-run して確認）。

| 項目 | 値 |
|---|---|
| ワークフロー実行 | `deploy` / `deploy_dev` への push（[run 38504976470](https://github.com/gyokuou0836/github_actions_for_aws/actions/runs/38504976470)）/ conclusion **`success`** |
| スタック | `s3-practice-dev` — **`CREATE_COMPLETE`**（2026-10-14 03:36:06 UTC = 12:36 JST） |
| リソース | `PracticeBucket` — `CREATE_COMPLETE` |
| 出力 | `BucketArn = arn:aws:s3:::ntcs-wan-s3-practice-wangyu-526034` |
| 認証 | `aws-actions/configure-aws-credentials` が OIDC（`sts:AssumeRoleWithWebIdentity`）で引受けに成功 |

検証コマンド（`ntcs-wan` でも実行可）:

```bash
aws cloudformation describe-stacks --stack-name s3-practice-dev --region ap-northeast-1 \
  --profile wangyu-mfa --query 'Stacks[0].{Status:StackStatus,Created:CreationTime,Outputs:Outputs}'
aws cloudformation describe-stack-events --stack-name s3-practice-dev --region ap-northeast-1 \
  --profile wangyu-mfa --max-items 5
aws s3api head-bucket --bucket ntcs-wan-s3-practice-wangyu-526034 --profile wangyu-mfa
```

### 再実行（Re-run）したときの挙動

`scripts/deploy.py` はスタックの有無で `create_stack` / `update_stack` を切り替え、
変更が無ければ CloudFormation の `No updates are to be performed` を捕まえて **`No changes.` で正常終了**します。

| 再実行の状況 | 動作 | バケット |
|---|---|---|
| **変更なしで再実行**（同じコミットの Re-run） | UpdateStack が「No updates are to be performed」→ `No changes.` で成功 | **無傷**（`LastUpdatedTime` も変化しない） |
| `cfn/s3-bucket.yaml` を変更 | 差分のみ反映（in-place） | 同じバケットのまま。オブジェクトも保持 |
| `vars.BUCKET_NAME` を変更 | `BucketName` が変わるため**置換**。旧バケットは `UpdateReplacePolicy: Retain` で残る | 新バケット作成・旧は孤児化（手動削除。データ移行も手動） |
| 途中で失敗 | 自動ロールバック。作成失敗→`ROLLBACK_COMPLETE`（更新不可）、更新失敗→`UPDATE_ROLLBACK_COMPLETE`（再更新可） | 作成前なら影響なし |
| 手動でスタックを delete してから再実行 | バケットが Retain で残るため同名作成が `BucketAlreadyExists` で `CREATE_FAILED` | 手動でバケットを消してから戻す必要あり |

> ロール権限には `s3:DeleteBucket` / `s3:DeleteObject` / `cloudformation:DeleteStack` が**含まれていません**
> （`github-actions-s3-practice-deploy-policy`）。そのため再実行でバケットやデータが消えることは仕組み上ありません。
> `cfn/s3-bucket.yaml` 側も `DeletionPolicy: Retain` / `UpdateReplacePolicy: Retain` を指定しています。

## 流れ
`feature/wangyu` で編集 → `deploy_dev` へPR → Merge → Actionsがdevスタックを更新

## トラブルシューティング

### `Not authorized to perform sts:AssumeRoleWithWebIdentity`

このリポジトリは GitHub OIDC の **immutable subject**（数値ID付き）を発行します。

```
repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev
```

この `sub` のうち **`@5299457`（オーナー/アカウント ID）と `@1416525375`（リポジトリ ID）は固定値**です。
**環境やブランチによって変わるのは最後の `:` 以降だけ**で、どちらの ID も GitHub が発行する不変識別子です。

| 部分 | 値 | 環境ごとに変わるか |
|---|---|---|
| `gyokuou0836@5299457` | オーナー名 @ **アカウント ID**（このアカウント配下の全リポジトリで共通） | ❌ 変わらない |
| `github_actions_for_aws@1416525375` | リポジトリ名 @ **リポジトリ ID**（GitHub 全体で一意） | ❌ 変わらない |
| `:environment:dev` | ジョブの Environment（`deploy.yml` の `environment:`） | ✅ **ここだけ変わる** |

| 実行 | 期待される `sub` |
|---|---|
| `deploy_dev` へ push（Environment `dev`） | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:dev` |
| `deploy_stg` へ push（Environment `staging`） | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:staging` |
| `workflow_dispatch` で `prod` | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:environment:prod` |
| Environment を使わないジョブ | `repo:gyokuou0836@5299457/github_actions_for_aws@1416525375:ref:refs/heads/deploy_dev` |

> ワークフローの `Show Expected OIDC Subject` ステップは `github.repository_owner_id` /
> `github.repository_id`（＝上記の固定 ID）をそのまま使い、`environment:` の部分だけを環境名で組み立てています。
> リポジトリ名やアカウント名を**リネームしても ID は変わりません**（変わるのは名前の部分だけ）。
> ID が変わるのは **別アカウントへのリポジトリ移転（transfer）や fork** をした場合です。

ID は認証不要の GitHub API でも確認できます（2026-10-14 実測: オーナー `5299457` / リポジトリ `1416525375`）。

```bash
curl -s https://api.github.com/repos/gyokuou0836/github_actions_for_aws | grep -E '"id"|"login"'
```

ロールの信頼ポリシーが旧形式（`repo:gyokuou0836/github_actions_for_aws:*` など）のままだと
`sub` が一致せず AssumeRole に失敗します。実環境のロール ARN・現在の信頼ポリシー・更新手順は
[`iam/README.md`](iam/README.md) を参照してください。

> **2026-10-14 時点で信頼ポリシーは immutable 形式に更新済みです**（`aws iam get-role` で実測確認済み）。
> Actions ログの実トークン `sub` と期待値が一致していることも確認済みで、**残作業は Actions の再実行のみ**です。
>
> デプロイロールは `arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy`（環境サフィックス無し）。
> 更新時は `ntcs-wan` では `NTCSDevGuardrailDenyPolicy` の `DenyTrustRelationshipTampering` により
> `iam:UpdateAssumeRolePolicy` が Deny されるため、管理者ユーザーに依頼してください。
>
> ワークフローの「Debug OIDC Token Claims」「Show Expected OIDC Subject」ステップで、
> 実際に発行された `sub` と信頼ポリシーが必要とする `sub` をログで比較できます
> （切り分けが完了したら削除して構いません）。

### `Failed to create the changeset: ... AWS::EarlyValidation::ResourceExistenceCheck ... FAILED`

`iam/github-oidc-role.yaml` を `cloudformation deploy` した際にこのエラーが出る場合、
パラメータ `CreateOidcProvider` が既定値 `true` のままで、既存の OIDC プロバイダと
**名前衝突**しています。`aws cloudformation describe-events` で次のように確認できます。

```
ValidationName: NAME_CONFLICT_VALIDATION
LogicalResourceId: GitHubOidcProvider (AWS::IAM::OIDCProvider)
"Resource of type 'AWS::IAM::OIDCProvider' with identifier
 'arn:aws:iam::646977526034:oidc-provider/token.actions.githubusercontent.com' already exists."
```

OIDC プロバイダはアカウントに 1 つしか作成できないため、既に存在する場合は
`CreateOidcProvider=false` を指定します（`iam/README.md` の「方法B」も同様）。

```
aws cloudformation deploy --region ap-northeast-1 \
  --stack-name github-oidc-s3-practice-dev \
  --template-file iam/github-oidc-role.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides EnvironmentName=dev CreateOidcProvider=false
```

> このコマンドは `AWS::IAM::Role` の作成を伴うため `iam:CreateRole` が必要です。
> `ntcs-wan` で実行すると `DeployRole`（`AWS::IAM::Role`）が次の理由で `CREATE_FAILED` になります。
>
> ```
> User: arn:aws:iam::646977526034:user/ntcs-wan is not authorized to perform: iam:CreateRole
> on resource: arn:aws:iam::646977526034:role/github-actions-s3-practice-deploy-dev
> with an explicit deny in an identity-based policy:
> arn:aws:iam::646977526034:policy/NTCSDevGuardrailDenyPolicy
> ```
>
> これは `NTCSDevGuardrailDenyPolicy` の `DenyUserAndGroupManagement` によるもので、
> **管理者ユーザーで実行**してください。
>
> 失敗するとスタックが残ります。changeset 作成前の失敗ではリソース 0 個の
> `REVIEW_IN_PROGRESS`、実行中の失敗では `ROLLBACK_COMPLETE` になり、どちらも更新不可なので
> `aws cloudformation delete-stack --stack-name github-oidc-s3-practice-dev` で削除します。

#### `ntcs-wan` のまま進める場合（IAM 変更だけを管理者に依頼する）

本リポジトリは「権限を絞られた開発者が、IAM の変更だけを管理者に依頼する」社用環境を擬似します。
`ntcs-wan` は必要な権限を持たないため、**依頼者側の作業はここで止め、次の内容を管理者に渡します**。

| # | 依頼内容 | 根拠 |
|---|---|---|
| 1 | 既存ロール `github-actions-s3-practice-deploy` の信頼ポリシー更新（方法A） | `iam:UpdateAssumeRolePolicy` が Deny（`DenyTrustRelationshipTampering`） |
| 2 | （任意）`github-oidc-role.yaml` によるロール作成（方法B） | `iam:CreateRole` ほか計 5 アクションが Deny／Allow 無し |

必要なアクションの洗い出し・差分 JSON・影響範囲・検証手順は
[`iam/README.md`](iam/README.md) の「提出用サマリ」「足りない権限の整理」にまとめてあります。
チケットには「提出用サマリ」のブロックをそのまま貼り付けられます。

管理者側がコマンドで実施する場合（管理者が SSO の `AdministratorAccess` を使える場合）の例:

```
aws configure sso --profile admin   # アカウント 646977526034 / ロール AdministratorAccess を選択
aws sso login --profile admin
aws iam update-assume-role-policy --role-name github-actions-s3-practice-deploy \
  --policy-document file://trust-policy.json --profile admin
```

> `ntcs-wan` に権限を追加して解決する案は採りません。`NTCSDevGuardrailDenyPolicy` の
> 条件なし Deny を緩める必要があり、本リポジトリの前提（権限分離の擬似）が崩れるためです
> （詳細は `iam/README.md` の「`ntcs-wan` に権限を付与する案を採らない理由」を参照）。

### `Warning: Node.js 20 is deprecated`（deploy ジョブの末尾）

ジョブが**成功していても**末尾に出る警告です（失敗ではありません）。初回デプロイ成功時にも出力されました。

```text
Warning: Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to
run on Node.js 24: actions/checkout@v4, actions/setup-python@v5, aws-actions/configure-aws-credentials@v4.
```

ランナー側は 2026-09-23 に Node 20 を削除済みのため、`node20` を宣言しているアクションは
Node 24 上で**強制実行**され、その旨が通知されます（動作自体は継続し、失敗にはなりません）。
対処は**アクションを Node 24 対応のメジャーへ上げるだけ**で、2026-10-14 に更新済みです。

| アクション | 変更前 | 変更後 | アクションの `runs.using` |
|---|---|---|---|
| `actions/checkout` | `@v4` | **`@v7`** | `node24` |
| `actions/setup-python` | `@v5` | **`@v7`** | `node24` |
| `aws-actions/configure-aws-credentials` | `@v4` | **`@v6`** | `node24` |

> ⚠️ `aws-actions/configure-aws-credentials@v5` は**まだ `node20`** です。Node 24 対応は `v6` です
> （`v6` はランナー `v2.327.1` 以上が要件。GitHub ホステッドランナーは充足しています）。

更新時に確認した破壊的変更と、本ワークフローへの影響:

| 変更 | 内容 | 本ワークフローへの影響 |
|---|---|---|
| `checkout@v6` | 認証情報の保存先が `.git/config` に変更 | なし（`persist-credentials` 未使用） |
| `checkout@v7` | fork からの PR でのチェックアウト制限 | なし（fork を使っていない） |
| `setup-python@v7` | `pip-install` 入力の削除 | なし（未使用） |
| `configure-aws-credentials@v6` | `node24` 化と入力バリデーション強化 | なし（使用中の入力はすべて有効） |

更新後もバケット／スタックの状態は変わりません（`scripts/deploy.py` が
`No updates are to be performed` を `No changes.` として正常終了させるため）。

