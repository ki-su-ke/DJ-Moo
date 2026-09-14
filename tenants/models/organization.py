from django.db import models
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel

from core.models import BaseModel


class Organization(SafeDeleteModel, BaseModel):
    """
    テナント 組織としての概念モデル
    """

    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=255)
    """ 組織名 """

    slug = models.SlugField(max_length=100, unique=True)
    """ スラッグ slugは論理削除済みも含めて再利用不可 """

    class Meta(BaseModel.Meta):
        db_table = "tenants_organization"
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self) -> str:
        return self.name
