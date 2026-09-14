# マルチテナント RBAC システム仕様書（確定版

ここはもう少し簡略化しておこう。
詳細は specification_detail.md に移動させるように。

## 1. 前提と方針

### 1-1. 前提条件

| 項目 | 内容 |
|------|------|
| テナント単位 | Organization |
| ユーザー所属 | 1 User が複数 Organization に所属可能 |
| 権限付与先 | Membership（User 直付け禁止） |
| Role の性質 | Permission の集合。Organization ごとに管理 |
| Permission の性質 | システム共通マスタ。`resource.action` 形式 |
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

#### 全モデル共通の基底モデルとして

UUIDによる主キー、作成日時・更新日時の自動管理を盛り込むこととする。  
また、META情報として、 `ordering = ["-created_at"]` を設定することで、デフォルトで作成日時順にソートされるようにする。  
メリットとしては、クエリセットをデフォルトで作成日時順にソートできるため、コードの簡潔さと一貫性が向上する。忘れやすい部分でもあるし、おかしなクエリを防ぐことができる。  


#### User
Django 標準ユーザーモデルを使用。`is_superuser` フラグを持つ。

#### Organization
| フィールド | 型 | 備考 |
|-----------|-----|------|
| name | CharField | 組織名 |
| slug | SlugField | 公開識別子。論理削除済みも含め再利用不可 |
| deleted | DateTimeField | django-safedelete による論理削除時刻 |

#### Membership
| フィールド | 型 | 備考 |
|-----------|-----|------|
| user | ForeignKey(User) | |
| organization | ForeignKey(Organization) | |
| roles | ManyToManyField(Role) | 複数 Role 所持可能 |
| scope_type | CharField | `all` または `assigned` |
| is_org_admin | BooleanField | Organization 管理者フラグ |
| deleted | DateTimeField | 論理削除時刻 |

制約：
- `user` と `organization` はユニーク（1人が同じ Organization に重複所属不可）
- `is_org_admin=True` の Membership が Organization 内に必ず1人以上存在することを強制する

#### Role
| フィールド | 型 | 備考 |
|-----------|-----|------|
| organization | ForeignKey(Organization) | 所属 Organization |
| name | CharField | 例：`Admin`, `Editor`, `Viewer` |
| permissions | ManyToManyField(Permission) | |
| deleted | DateTimeField | 論理削除時刻 |

#### Permission（システム共通マスタ）
| フィールド | 型 | 備考 |
|-----------|-----|------|
| resource | CharField | リソース名(`product`など) |
| action | CharField | 操作名 |
| name | CharField | 表示名 |

#### Product
| フィールド | 型 | 備考 |
|-----------|-----|------|
| organization | ForeignKey(Organization) | テナント境界 |
| name | CharField | |
| assignees | ManyToManyField(Membership) | `assigned` スコープ判定用 |
| created_by | ForeignKey(Membership) | 作成者。監査ログ用途 |
| deleted | DateTimeField | 論理削除時刻 |

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

`is_org_admin=True` は以下の操作を許可する。これは Permission 体系とは別の独立したフラグとする。

- Membership の招待・削除
- Organization 設定の変更
- Role の作成・編集・削除

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

`scope_type=assigned` の Membership が Product を作成した場合、作成者を自動的に `assignees` に追加する。`created_by` は監査ログ用途として記録するが、アクセス制御には `assignees` のみを使用す。

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

```python
class ProductQuerySet(models.QuerySet):
    def for_membership(self, membership):
        qs = self.filter(organization=membership.organization)

        if membership.user.is_superuser:
            return qs

        if membership.scope_type == "assigned":
            qs = qs.filter(assignees=membership)

        return qs
```

ビュー内では常に `Product.objects.for_membership(request.membership)` を使用する。

---

## 10. 初期データ（シード）

### 10-1. Permission マスタ

`product.view`, `product.create`, `product.update`, `product.delete` をシステム共通マスタとして fixtures またはマイグレーションで投入する。将来のリソース追加時も同じ `resource.action` 形式で追加する。

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
Organization 管理者（Admin Role 所持者）は product.view_deleted と product.restore によって、論理削除済み Product の閲覧・復元が可能とする。Editor・Viewer には該当 Permission を付与しない。

----

## 12 セキュリティイベント監査（追加）
テナント境界違反や権限不足によるアクセス拒否が発生した場合、SecurityEvent モデルにイベントを記録する。同一ユーザー・IP からの継続的な不正アクセス試行を検知できる構造とし、将来的なレート制限やアラート機能への拡張を見据える。

現段階でのイメージは以下の通り：

```python
class SecurityEvent(models.Model):
    EVENT_TYPES = [
        ('tenant_escape', 'テナント境界違反試行'),
        ('permission_denied', '権限不足アクセス試行'),
        ('deleted_data_access', '論理削除済みデータアクセス試行'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    attempted_organization_slug = models.SlugField()  # URLに含まれていたslug
    target_resource = models.CharField(max_length=100)  # product など
    target_resource_id = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)
    count = models.PositiveIntegerField(default=1)  # 同条件での集計用
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'event_type', 'timestamp']),
            models.Index(fields=['ip_address', 'event_type', 'timestamp']),
        ]
```

このようなテーブルを追加し、アクセス制御のロジックの中でイベントを記録する。
DRF のカスタム Permission クラスまたはミドルウェアでフックするという形か。

```python
# カスタム Permission クラスのイメージ
class TenantPermission(BasePermission):
    def has_permission(self, request, view):
        organization = request.organization
        membership = request.membership
        
        # テナント境界チェック：URLのorganizationと対象データのorganizationが一致するか
        # （ビュー内でチェックする場合は has_object_permission で）
        
        if not membership and not request.user.is_superuser:
            # テナント跨ぎ疑いのイベントを記録
            SecurityEvent.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=get_client_ip(request),
                event_type='tenant_escape',
                attempted_organization_slug=view.kwargs.get('organization_slug'),
                target_resource=view.basename or 'unknown'
            )
            return False
            
        return True
```

パターンA：イベントごとに1レコード（履歴重視）  
毎回 create する  
後で COUNT(*) GROUP BY user, DATE(timestamp) で集計  

という形で行くこととする。  

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
| BaseModel | 各アプリに共通なモデルをcoreアプリに置くのが Django 慣習 |

現時点ではBaseModelしか該当しないが、将来的に他の要素を増やす可能性もあり。

#### accounts：ユザーと認証

| 配置するもの | 理由 |
|-----------|------|
| Custom User モデル | カスタムUserは独立したアプリに置くのが Django 慣習 |
| `auth.py`（カスタム認証クラス） | DRF の認証バックエンド拡張があればここ |
| JWT 設定（SimpleJWT を使う場合） | 設定は `config/settings.py`、カスタム処理があればここ |

認証部を独立アプリにする必要はない。DRF + SimpleJWT を使うなら `accounts` にまとめて十分。カスタム認証バックエンドやログイン/ログアウト API もここに置く。

---

#### tenants：テナントと RBAC の基盤

| 配置するもの | 理由 |
|-----------|------|
| Organization, Membership, Role, Permission モデル | テナントと権限は密結合なので同じアプリ |
| `middleware.py` | `request.organization` / `request.membership` の解決 |
| `permissions.py` | DRF のカスタム Permission クラス（TenantPermission, RBACPermission） |
| `seed.py` | Organization 作成時の Role シード処理 |
| `signals.py` | Organization 作成時の自動処理フック |

RBAC を `tenants` に入れる理由：Role・Permission・Membership は Organization（テナント）と切り離せないため、同じアプリにまとめることで循環インポートを防ぐ。

---

#### products：業務データ

| 配置するもの | 理由 |
|-----------|------|
| Product モデル | 初期保護対象リソース |
| `querysets.py` | `ProductQuerySet.for_membership()` の定義 |
| `views.py`（ViewSet） | Product CRUD + restore/hard_delete アクション |
| `serializers.py` | シリアライザー |

Product モデルを `products` に置く理由：将来的に Order, Report などが増えた時に、業務ドメインごとにアプリを分離しやすい。今は Product だけでも、テナント基盤と業務データを分離しておくと後々きれいになる。

---

#### audit：セキュリティイベント監査

| 配置するもの | 理由 |
|-----------|------|
| SecurityEvent モデル | セキュリティイベントの永続化 |
| `recorder.py` | イベント記録用のユーティリティ関数 |
| `admin.py` | 管理画面での閲覧用（スーーユーザー専用） |

独立アプリにする理由：セキュリティイベントはテナントにも業務データにも依存しない横断的関心事。独立させることで、どのアプリからでも呼び出せて、循環インポートが起きない。

---

### ファイル配置（主要部分）

```
config/
├── settings.py
├── urls.py
└── middleware.py              # テナント解決ミドルウェア（tenants/middleware.py から import してもOK）

accounts/
├── models.py                  # Custom User
├── views.py                   # ログイン/ログアウト API（あれば）
└── auth.py                    # カスタム認証クラス（あれば）

tenants/
├── models.py                  # Organization, Membership, Role, Permission
├── permissions.py             # DRF TenantPermission, RBACPermission
├── middleware.py              # TenantResolutionMiddleware
├── seed.py                    # create_default_roles(), create_org_with_admin()
└── signals.py                 # Organization 作成後の Role シード

products/
├── models.py                  # Product（QuerySet もここで定義）
├── views.py                   # ProductViewSet
└── serializers.py

audit/
├── models.py                  # SecurityEvent
├── recorder.py                # record_security_event()
└── admin.py
```


----

## 14. 将来拡張

- スコープ：`own`（`created_by` ベース）、`category`（カテゴリ単位の可視範囲）への拡張を想定した構造とする
- リソース：Product 以外のリソース（Order, Report などを追加する際も `resource.action` 形式で Permission を追加し、同じ RBAC 体系で制御する
- 論理削除復元：`product.restore` などの復元 Permission を追加し、復元操作を権限管理下に置く

