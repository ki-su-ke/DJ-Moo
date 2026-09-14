# DJ-Moo

## 概要

Djangoによるマルチテナントモデルのサンプルとして。  
実際に業務で扱う中で、上手く行った部分、上手く行かなった部分が当然ありました。
今回はそれらを踏まえて、「こうやったらいいのでは？」という形を自分なりに形にしていきたいと思います。  

盛り込む要素としては以下の通りです。  

- テナント境界をOrganizationとして管理
- RBAC(Role Based Access Control)＋スコープによるアクセス制御
- JWT認証をベースとして、MFA認証とパスキー認証もサポート
- 論理削除


環境は、Django 5.2(LTS)を基準にしていきます。Pythonのバージョンは3.12以上を想定とします。  

個人的なサブテーマとして、論理削除をライブラリで行うというものがあります。  
かつて、まだあまり定番のライブラリが無かったため、自前で実装していた経験があります。
それは今でも本番稼働中のアプリで使われていますし、使い勝手もDjango標準のクエリセットと同等になるように設計しましたし(チームだと重要ですよね)、機能面でも削除時にリレーションを追ってちゃんと処理するようにした力作ではあるのですが、最近は定番と呼べるライブラリが出てきているようだと耳にしたので試してみようというわけです。  

ちょっと思いついた部分としては、セキュリティ観点で将来的に使えそうだし重要そうだなと感じたので、不正にテナントを跨いだ場合のログを記録する仕組みを入れてみました。  
こういう元となるデータって後から対応しづらいし、最初からあったらよかったのに！と思う所だと思うので、お試しにという感じです。  
あまりこだわると色々大変そうなので、今回はシンプルに「テナントを不正に跨ごうとした悪いやつ炙り出し専門」としました。  

ちなみに、頑張ってひねり出したプロジェクト名は「DJ-Moo」です。  
DjangoだからDJ-にしようと思って、後はKOOしか思いつかないのをなんとかMOOにしました。
Django Multi-tenant Organization Orchestration の略だとしておいてください。  


## 仕様

詳しい仕様は [specification.md](specification.md) を参照してください。  


## 構成

仕様に従い、以下の構成としました。

```
dj-moo/
├── core/              # BaseModel(全モデルに共通の基底モデル)を置く
├── accounts/          # カスタムUser + 認証
├── tenants/           # Organization, Membership, Role, Permission, RBAC基盤
├── products/          # Product（保護対象業務データ）
├── audit/             # SecurityEvent（セキュリティイベント監査）
└── config/            # settings, urls, ミドルウェア, DRF設定
```

一般的にどうかは置いておいて、仕様をある程度決めたらDockerで管理することを含めて構成を作っちゃうのが楽というか取っ散らからないことにつながると思うので、ここまで一気呵成にまとめ上げました。  
実務でも毎回こうできるときれいに収まりそうなんですけどね。  
ちなみに、今回のように構成ファーストでやった場合、docker-compose.yamlとかDockerileと同階層にstartprojectして、同じく同階層にstartappしていくといい感じにまとまるというかDjangoっぽい流儀になると思います。  

---

## memo

- Userモデルは、不要になりそうなフィールドを残すのもなんなので、AbstractBaseUserを継承することとする

- 認証もRBACも・・となると色々きつそうなのでRBAC基盤の実装を優先とする　認証機構は、まずはJWTとして、それが済み次第再度検討しつつ進めよう

- 設計で気を使った点
    - DJ-Mooの設計思想として、
    「テナント境界を後からチェックするのではなく、モデルの関係としてできるだけ自然に閉じ込める」
    という点に気を使いました。
    通常ならば、UserにRoleなどを結び付け、Organizationを見ながら権限をチェックする・・・という構図になりがちです。
    今回は、UserのOrganizationへの所属をMembershipとして表現し、RoleもMembershipに対して割り当てる形としました。
    さらに、OrganizationとMembershipとRoleの関係にはMembershipRoleを挟むことで、MembershipとRoleが同一Organizationに属することを前提とした、より厳格な構造としています。

    - 


- 今回のプロジェクトを終えて
    - User と Organization の所属をどう表現するか
    - Role をどこにぶら下げるか
    - Organization 境界をどう保証するか
    - Permission を共通化するか
    - 論理削除をどう扱うか
    - 認証・認可をどう分離するか
    - 不正なテナント跨ぎをどう検知・記録するか

    みたいな、現場で普通に悩みそうなポイントに自分なりの答えが出せたかなと思います。
    そして、「この関係にしておけば、そもそも変な状態を作りにくいんじゃないか？」という形にまで昇華できたかなと。
    いわば 「業務システムで使える構成を、余計な業務ロジックを削って公開可能な形にした」 と言えそうですね。  
    そういう意味で、自分にとっても勉強になりました。  
    ※そして論理削除の比較についても触れておこう
---
---

Django 5 上で、単一基盤・単一DBに複数 Organization を同居させつつ、Organization 単位で厳密にデータ分離し、RBAC + スコープ制御でアクセス権を管理するための仕様案です。

今回の前提は以下で確定とします。

- テナント単位は Organization
- ユーザーは複数 Organization に所属可能
- 権限は User 直付けではなく Membership に付与
- Role は Permission の集合
- Permission はシステム共通マスタ
- Role は Organization ごとに管理
- アクセス制御は テナント境界 + Permission + スコープ
- URL は Organization の公開識別子 slug/UUID を含める方式
- 初期保護対象は Product


### 用語定義

#### User
    ログイン主体となるアカウント。  
    個人そのものを表す。  
    
#### Organization
    テナント。  
    業務データの境界単位。  

#### Membership
    User が Organization に所属している関係。  
    権限付与の主体は User ではなく Membership。  
    
#### Permission
    一般化された操作権限。  
    resource.action 形式で管理する。  
    例:  
        product.view  
        product.create  
        product.update  
        product.delete  

#### Role
    Permission の集合。  
    Organization ごとに保持する。  

#### Scope
    Permission を行使できるデータ範囲。  
    例:  
    all  
    assigned  

#### Product
    Organization 配下の保護対象データ。  
    初期実装の対象業務データ。  


### 基本方針

#### 2-1. テナント分離

すべての業務データは必ず 1 つの Organization に属する  
A Organization 所属ユーザーは、B Organization のデータを参照・更新・削除できない  
この制約は UI ではなくサーバ側で強制する  

##### 2-2. 権限管理  
認証は Django 標準認証基盤を利用する  
認可は Django の auth.Permission ではなく自前 RBAC で管理する  
Permission はシステム共通語彙として固定する  
Role は Organization ごとに作成・編集可能とする  

##### 2-3. スコープ制御  
Role/Permission に加え、データの可視範囲を制御する  
初期実装では all と assigned をサポートする  
将来的に category, own へ拡張可能な構造とする  

----
----
----


