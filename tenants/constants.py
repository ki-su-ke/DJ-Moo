#
# Organization作成時に用意したい初期装備用Roleを定義しておく
#
# まずはPermissionモデルのresourceとactionの組み合わせを定義する
# ここではconst代わりにdataclassを使ってみよう
# 変えてほしくない(変わってほしくない)部分はdataclassとして、
# 設定定義的な部分は辞書形式で柔軟に　というのはいい形っぽい
#
from dataclasses import dataclass

@dataclass(frozen=True)
class PermissionKey:
    """
    Permissionテーブルのカラム名と値のセットを定義
    """
    res_product: str = "product"
    res_membership: str = "membership"
    res_role: str = "role"

    act_manage: str = "manage"
    act_assign: str = "assign"
    act_view: str = "view"
    act_create: str = "create"
    act_update: str = "update"
    act_delete: str = "delete"
    act_view_deleted: str = "view_deleted"
    act_restore: str = "restore"


@dataclass(frozen=True)
class RoleDefaultName:
    """
    デフォルトで設定したいRole名称
    """
    ADMIN: str = "Admin"
    EDITOR: str = "Editor"
    VIEWER: str = "Viewer"


DEFAULT_ROLE_PERMISSION_KEYS = {
    RoleDefaultName.ADMIN: [
        (PermissionKey.res_product, PermissionKey.act_view),
        (PermissionKey.res_product, PermissionKey.act_create),
        (PermissionKey.res_product, PermissionKey.act_update),
        (PermissionKey.res_product, PermissionKey.act_delete),
        (PermissionKey.res_product, PermissionKey.act_view_deleted),
        (PermissionKey.res_product, PermissionKey.act_restore),
        (PermissionKey.res_membership, PermissionKey.act_manage),
        (PermissionKey.res_role, PermissionKey.act_manage),
        (PermissionKey.res_role, PermissionKey.act_assign),
    ],
    RoleDefaultName.EDITOR: [
        (PermissionKey.res_product, PermissionKey.act_view),
        (PermissionKey.res_product, PermissionKey.act_create),
        (PermissionKey.res_product, PermissionKey.act_update),
    ],
    RoleDefaultName.VIEWER: [
        (PermissionKey.res_product, PermissionKey.act_view),
    ],
    
}
"""
Organizationモデルの作成時に、デフォルトで付与したいRole名称とPermissionのセットを定義
"""
