# Permissionの規定値について

## Permissionの規定値(初期値)は以下のように規定する

| resource | 取り得る規定値の範囲 |
| --- | --- |
| Product | 1 - 100 |
| Organization | 101-199(100番台) |
| Membership | 201-299(200番台) |
| Role | 301-399(300番台) |

サンプルは以下の通り

```json
[
  // 既存のProduct関連（001-006番台）
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000001",
    "fields": {
      "resource": "product",
      "action": "view",
      "name": "製品の閲覧"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000002",
    "fields": {
      "resource": "product",
      "action": "create",
      "name": "製品の作成"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000003",
    "fields": {
      "resource": "product",
      "action": "update",
      "name": "製品の更新"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000004",
    "fields": {
      "resource": "product",
      "action": "delete",
      "name": "製品の削除"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000005",
    "fields": {
      "resource": "product",
      "action": "view_deleted",
      "name": "削除済み製品の閲覧"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000006",
    "fields": {
      "resource": "product",
      "action": "restore",
      "name": "製品の復元"
    }
  },
  
  // Organization関連（101-199番台）
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000101",
    "fields": {
      "resource": "organization",
      "action": "manage",
      "name": "組織設定の管理"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000102",
    "fields": {
      "resource": "organization",
      "action": "view",
      "name": "組織情報の閲覧"
    }
  },
  
  // Membership関連（201-299番台）
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000201",
    "fields": {
      "resource": "membership",
      "action": "invite",
      "name": "メンバー招待"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000202",
    "fields": {
      "resource": "membership",
      "action": "remove",
      "name": "メンバー削除"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000203",
    "fields": {
      "resource": "membership",
      "action": "manage",
      "name": "メンバーシップ管理"
    }
  },
  
  // Role関連（301-399番台）
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000301",
    "fields": {
      "resource": "role",
      "action": "manage",
      "name": "ロール管理"
    }
  },
  {
    "model": "tenants.permission",
    "pk": "00000000-0000-0000-0000-000000000302",
    "fields": {
      "resource": "role",
      "action": "assign",
      "name": "ロール割り当て"
    }
  }
]
```