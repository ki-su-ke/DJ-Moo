# マルチテナント RBAC システム仕様書（確定版

ここはもう少し簡略化しておこう。
詳細は specification_detail.md に移動させるように。

## 1. 前提と方針

### 1-1. 前提条件

| 項目 | 内容 |
|------|------|
| テナント単位 | Organization |
| ユーザー所属 | 1 User が複数 Organization に所属可能 |
| 権限付与先 | Membership（UserはMembershipを通してOrganizationに所属する） |
| Role の性質 | Permission の集合。Organization ごとに管理 |
| Permission の性質 | システム共通マスタ。 |
| アクセス制御 | テナント境界 + Permission + スコープの3層 |
| URL 設計 | `/{organization_slug}/...` に Organization の公開識別子を含める |
| 初期保護対象 | Product |

### 1-2. 基本方針

- すべての業務データは必ず1つの Organization に属する
- A Organization 所属ユーザーは、B Organization のデータを参照・更新・削除できない
- この制約は UI ではなくサーバ側で強制する
- 認証は Django 標準認証基盤を利用する
- 認可は Django の `auth.Permission` ではなく自前 RBAC で管理する
- スコープは `all` / `assigned` を初期実装とし、将来的に `own`, `category` などへ拡張可能な構造とる

---

## 2. 用語定義

### 2-1. User
ログイン主体となるアカウント。個人そのものを表す。

### 2-2. Organization
テナント。業務データの境界単位。

### 2-3. Membership
User が Organization に所属している関係。中間テーブルとして明示的にモデル化し、追加属性（Role、スコープ、管理者フラグ）を持つ。権限付与の主体は User ではなく Membership である。

### 2-4. Permission
~~一般化された操作権限。`resource.action` 形式で管理する。~~
~~例：~~
~~- `product.view`~~
~~- `product.create`~~
~~- `product.update`~~
~~- `product.delete`~~
~~- `product.view_deleted`~~
~~- `product.restore`~~

一般化された操作権限。対象'resource'と操作'action'の組み合わせで表現する。
- `resource` は `product` などのリソース名
- `action` は `view`, `create`, `update`, `delete`, `view_deleted`, `restore` などの操作名称  
`view_deleted`は論理削除されたリソースへの閲覧権限, `restore`は論理削除されたリソースの復元権限。  

### 2-5. Role
Permission の集合。Organization ごとに作成・編集可能。1つの Membership は複数の Role を持てる。

### 2-6. Scope
Permission を行使できるデータ範囲。

| スコープ | 意味 |
|---------|------|
| `all` | Organization 内の該当リソース全件にアクセス可能 |
| `assigned` | 自身の Membership が assignee として紐いているデータのみアクセス可能 |

### 2-7. Product
Organization 配下の保護対象データ。初期実装の対象業務リソース。

---

## 3. データモデル

### 3-1. リレーション概要

```text
User --------< Membership >-------- Organization
                    |
                    | 1:N
                    v
            MembershipRole
              ^       |
              |       v
         Membership   Role --------< Role.permissions >-------- Permission
                         |
                         v
                    Organization
```

### 文章でまとめると
User は Organization への所属を Membership として持つ。
権限は User に直接付かず、Membership に対して Role を割り当てる形で付与される。
Role は Organization ごとに定義される Permission の集合であり、Permission 自体はシステム共通マスタである。
Membership と Role の関係は MembershipRole で表し、この中間モデルで Membership と Role の Organization 一致を保証する。(テナント境界の厳守)
これにより、Organization ごとに閉じた RBAC を実現しつつ、1ユーザーが複数 Organization に所属しても、対象 Organization の Membership 単位で安全に権限判定できる。

### 3-2. 各モデル定義
長くなったので割愛。概要と特徴的なポイントだけ記載しておきます。

#### 全モデル共通の基底モデルとして

UUIDによる主キー、作成日時・更新日時の自動管理を盛り込むこととする。  
また、META情報として、 `ordering = ["-created_at"]` を設定することで、デフォルトで作成日時順にソートされるようにする。  
メリットとしては、クエリセットをデフォルトで作成日時順にソートできるため、コードの簡潔さと一貫性が向上する。忘れやすい部分でもあるし、おかしなクエリを防ぐことができる。  


#### User
Django 標準ユーザーモデルを使用。`is_superuser` フラグを持つ。

#### Organization
組織名のほかに、公開識別子として slug を持つ。

#### Membership
OrganizationとUserを結び付ける中間モデル。  
またRoleもここに付与される。  
AdminRoleを持つ管理者には、is_org_adminフラグをつける。  

制約：  
- 1人が同じ Organization に重複所属不可
- `is_org_admin=True` の Membership が Organization 内に必ず1人以上存在することを強制する  

#### Role
Role は Organization によって作成・管理され、Permission をまとめたものとする。  
同じ内容であっても、Organization 間で 同一Role の共有はなされない。  
Role は Membership を通じて付与される。  
所属がはっきりしているので、テナント独自ルールの追加が可能となる。  

#### Permission（システム共通マスタ）
システム共通マスタとして Permission は管理される。  
User  がこれを作成・編集することはできない。  


#### Product
Product は Organization に所属し、Organization を跨ぐことはできない。
Organization は Membership を通じて Product へのアクセス権をコントロールできる。

---

## 4. 権限管理

### 4-1. Permission チェックの原則

Permission チェックは **Role → Permission のみ**を参照する。  
`is_org_admin` フラグは Permission チェックに使用しない。

### 4-2. 有効 Permission の算出

Membership が持つ全 Role の Permission の和集合が、その Membership の有効 Permission となる。

```python
# 疑似コード
effective_permissions = Permission.objects.filter(
    role__membership=membership
).distinct()
```

※ ただし、有効 Permission は対象 Organization に対応する Membership ごとに算出する。User の全 Membership を横断して合算してはならない。

### 4-3. 組織管理権限（is_org_admin）

`is_org_admin=True` は以下の操作を許可する。

- Membership の招待・削除
- Organization 設定の変更
- Role の作成・編集・削除

is_org_admin は Role によって制御される。
Organization 内の `is_org_admin=True` の Membership は必ず1人以上存在することを強制する。最後の1人を削除・無効化しようとした場合はエラーとする。

### 4-4. スーパーユーザー（Django）

`is_superuser=True` の User は以下の特権を持つ。

- Organization を跨いで全データにアクセス可能
- 論理削除済みデータにもアクセス可能
- Role や Permission のチェックをスキップする
- ただし、テナント境界（どの Organization のデータか）は URL の `organization_slug` で明示するため、意図しない Organization のデータを操作することはない

---

## 5. スコープ制御

### 5-1. スコープの種類

| スコープ | 適用クエリ条件 |
|---------|--------------|
| `all` | `organization = 対象 Organization` のみ |
| `assigned` | `organization = 対象 Organization` かつ `assignees` に自身の Membership が含まれる |

### 5-2. アクセス判定フロー

1. テナント境界チェック：対象データの `organization` が URL の `organization_slug` で解決した Organization と一致するか
2. Permission チェック：要求されたアクションの Permission が `effective_permissions` に含まれるか
3. スコープチェック：
   - `all` → 許可
   - `assigned` → `assignees` に自身の Membership が含まれるか確認

### 5-3. Product 作成時の挙動

`scope_type=assigned` の Membership が Product を作成した場合、作成者を自動的に `assignees` に追加する。`created_by` は監査ログ用途として記録するが、アクセス制御には `assignees` のみを使用する。

---

## 6. 論理削除

### 6-1. 方針

django-safedelete を使用する。

| モデル | ポリシー | 理由 |
|--------|---------|------|
| Organization | `SOFT_DELETE_CASCADE` | Organization 論理削除時に Product・Membership も論理削除する |
| Membership | `SOFT_DELETE` | 論理削除された Membership は有効ではないためデータアクセス不可 |
| Product | `SOFT_DELETE` | 通常クエリから除外 |
| Role | `SOFT_DELETE` | 論理削除済み Role は有効 Membership から参照されない |

### 6-2. 削除済みデータへのアクセス

- 通常ユーザーは論理削除済みデータにアクセスできない（django-safedelete がデフォルトで除外するため）
- スーパーユーザーのみ `all_objects` を使って論理削除済みデータにアクセス可能

### 6-3. Organization slug の再利用

論理削除された Organization の slug は再利用不可とする。復元時に slug が奪われていると整合性が崩れるため。

---

## 7. URL 設計

```
/{organization_slug}/products/              → Product 一
/{organization_slug}/products/{product_id}/ → Product 詳細
```

### 7-1. テナント解決と権限チェックの流れ

1. ミドルウェアで URL の `organization_slug` から Organization を解決し、`request.organization` にセット
2. 同時に現在の User に対応する有効な Membership を取得し、`request.membership` にセット
3. DRF の Permission クラスで `request.membership` を参照し、必要な Permission が `effective_permissions` に含まれるかチェック
4. スーパーユーザーの場合は `request.membership` がなくてもアクセス許可（ただし `request.organization` はセットされる）

---

## 8. API レスポンス形式

Membership に紐づく権限情報を返す際、以下の構造とする。

```json
{
  "membership": {
    "id": "uuid",
    "scope_type": "assigned",
    "is_org_admin": false,
    "roles": [
      {
        "id": "role-1",
        "name": "Editor",
        "permissions": [
          {"codename": "product.view", "name": "製品の閲覧"},
          {"codename": "product.update", "name": "製品の更新"}
        ]
      }
    ],
    "effective_permissions": [
      {"codename": "product.view", "name": "製品の閲覧"},
      {"codename": "product.update", "name": "製品の更新"}
    ]
  }
}
```

- `roles`：UI で Role の割り当て/編集を表示するため
- `effective_permissions`：フロントエンドの画面制御（ボタン表示/非表示）とサーバ側の権限チェックの参照用

---

## 9. クエリセットの共通化

カスタム QuerySet に `for_membership(membership)` メソッドを定義し、テナント境界・スコープ・論理削除フィルタを一元化する。

ビュー内では常に `Product.objects.for_membership(request.membership)` を使用する。

---

## 10. 初期データ（シード）

### 10-1. Permission マスタ

システム共通マスタとして fixtures で投入する。
詳細は、[Permissionの規定値について.md](./Permissionの規定値について.md) を参照。

### 10-2. Organization 作成時の自動生成 Role

Organization 作成時に以下の Role を自動生成する。

| Role | 初期 Permission |
|------|----------------|
| Admin | 全 Permission |
| Editor | `product.view`, `product.create`, `product.update` |
| Viewer | `product.view` |

Organization の作成者には Admin Role を自動付与し、`is_org_admin=True` をセットする。

---

## 11 論理削除済みデータのアクセス制御（追加）
Organization 管理者（Admin Role 所持者）は product.view_deleted と product.restore によって、論理削除済み Product の閲覧・復元が可能とする。Editor・Viewer には該当 Permission を付与しない。(要検討)

----

## 12 セキュリティイベント監査
テナント境界違反や権限不足によるアクセス拒否が発生した場合、SecurityEvent モデルにイベントを記録する。同一ユーザー・IP からの継続的な不正アクセス試行を検知できる構造とし、将来的なレート制限やアラート機能への拡張を見据える。

この監査ログは COUNT(*) GROUP BY user, DATE(timestamp) のような形で集計可能。

----

## 13. プロジェクト構成

```
project/
├── core/              # BaseModel(全モデルに共通の基底モデル)を置く
├── accounts/          # カスタムUser + 認証
├── tenants/           # Organization, Membership, Role, Permission, RBAC基盤
├── products/          # Product（保護対象業務データ）
├── audit/             # SecurityEvent（セキュリティイベント監査）
└── config/            # settings, urls, ミドルウェア, DRF設定
```


### 各アプリの責務

#### core：各アプリに共通となるべき基底モデルを定義

| 配置するもの | 理由 |
|-----------|------|
| BaseModel | 各アプリに共通なモデルをcoreアプリに置く |

現時点ではBaseModelしか該当しないが、将来的に他の要素を増やす可能性もあり。

#### accounts：ユザーと認証

| 配置するもの | 理由 |
|-----------|------|
| Custom User モデル | カスタムUserは独立したアプリに置く |
| `auth.py`（カスタム認証クラス） | DRF の認証バックエンド拡張があればここ |
| JWT 設定（SimpleJWT を使う場合） | 設定は `config/settings.py`、カスタム処理があればここ |  

---

#### tenants：テナントと RBAC の基盤

| 配置するもの | 理由 |
|-----------|------|
| Organization, Membership, Role, Permission モデル | テナントと権限は密結合なので同じアプリ |
| middleware / service層 | テナント境界ルールの解決 |

RBAC を `tenants` に入れる理由：Role・Permission・Membership は Organization（テナント）と切り離せないため、同じアプリにまとめることで循環インポートを防ぐ。

---

#### products：業務データ

| 配置するもの | 理由 |
|-----------|------|
| Product モデル | 初期保護対象リソース |
| service層 | Product のロジックを管理 |

Product モデルを `products` に置く理由：将来的に Order, Report などが増えた時に、業務ドメインごとにアプリを分離しやすい。今は Product だけでも、テナント基盤と業務データを分離しておくと後々きれいになる。

---

#### audit：セキュリティイベント監査

| 配置するもの | 理由 |
|-----------|------|
| SecurityEvent モデル | セキュリティイベントの永続化 |
| service層 | イベント記録用のユーティリティ関数 |
| `admin.py` | 管理画面での閲覧用（スーパーユーザー専用） |

独立アプリにする理由：セキュリティイベントはテナントにも業務データにも依存しない横断的関心事。

---


----

## 14. 将来拡張

- スコープ：`own`（`created_by` ベース）、`category`（カテゴリ単位の可視範囲）への拡張を想定した構造とする
- リソース：Product 以外のリソース（Order, Report などを追加する際も `resource.action` 形式で Permission を追加し、同じ RBAC 体系で制御する
- 論理削除復元：`product.restore` などの復元 Permission を追加し、復元操作を権限管理下に置く

