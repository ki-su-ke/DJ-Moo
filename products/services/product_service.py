from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from django.core.exceptions import MultipleObjectsReturned

from products.models import Product, ProductAssignee, ProductStatus
from tenants.models import Membership, MembershipScope

import logging

logger = logging.getLogger(__name__)


class ProductService:
    """
    """

    @staticmethod
    def _ensure_same_organization(*, product: Product, membership: Membership):
        """
        ProductとMembershipが同じOrganizationに所属しているか確認する

        Args:
            product (Product): 対象のProduct
            membership (Membership): 対象のMembership

        Raises:
            ValidationError: ProductとMembershipが同じOrganizationに所属していない場合
        """
        if product.organization_id != membership.organization_id:
            logger.error(f"Product and Membership must belong to the same Organization.")
            raise ValidationError("ProductとMembershipは同じOrganizationに所属している必要があります。")

    @staticmethod
    @transaction.atomic
    def create_product(
            *,
            organization,
            name: str,
            created_by: Membership,
            description: str = "",
            status: str = ProductStatus.DRAFT,
            is_active: bool = True,
            assignees: list[Membership] | None = None,
        ) -> Product:
        """
        Productを作成する
        
        Args:
            organization: Organization
            name: Product名
            created_by: 作成者
            description: 説明
            status: ステータス
            is_active: アクティブかどうか
            assignees: 担当者リスト
            
        Returns:
            Product: 作成されたProduct
        
        raises: ValidationError etc
        """
        if organization.id != created_by.organization_id:
            logger.error(f"Organization and created_by(Membership) must belong to the same organization.", exc_info=True)
            raise ValidationError("ProductとOrganizationは同じOrganizationに所属している必要があります。")
        
        try:
            product = Product.objects.create(
                organization=organization,
                name=name,
                description=description,
                status=status,
                is_active=is_active,
                created_by=created_by,
            )

            if created_by.scope_type == MembershipScope.ASSIGNED:
                ProductAssignee.objects.get_or_create(
                    product=product,
                    membership=created_by
                )
            
            if assignees:
                for membership in assignees:
                    ProductService._ensure_same_organization(
                        product=product,
                        membership=membership
                    )
                    ProductAssignee.objects.get_or_create(
                        product=product,
                        membership=membership
                    )

            return product

        except IntegrityError as e:
            logger.error(f"Failed to create Product {name}: {str(e)}", exc_info=True)
            raise ValidationError(f"Product {name} の作成に失敗しました。")
        except MultipleObjectsReturned as e:
            logger.error(f"Failed to create Product {name}: {str(e)}", exc_info=True)
            raise ValidationError(f"Product {name} の作成に失敗しました。")
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Unexpected error occurred.", exc_info=True)
            raise

    @staticmethod
    @transaction.atomic
    def assign_membership(*, product: Product, membership: Membership) -> ProductAssignee:
        """
        ProductにMembershipを割り当てる

        Args:
            product (Product): 割り当てるProduct
            membership (Membership): 割り当てるMembership

        Returns:
            ProductAssignee: 割り当てられたProductAssignee

        Raises:
            ValidationError: 割り当てに失敗した場合
        """
        try:
            ProductService._ensure_same_organization(
                product=product,
                membership=membership
            )

            assignee, _ = ProductAssignee.objects.get_or_create(
                product=product,
                membership=membership
            )

            return assignee

        except IntegrityError as e:
            logger.error(f"Failed to assign_membership: Product {product.name} to Membership - {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError(f"Product {product.name}とMembershipの割り当てに失敗しました。")
        except MultipleObjectsReturned as e:
            logger.error(f"Failed to assign_membership: Product {product.name} to Membership - {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError(f"Product {product.name}とMembershipの割り当てに失敗しました。")
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Unexpected error occurred.", exc_info=True)
            raise

    @staticmethod
    @transaction.atomic
    def unassign_membership(*, product: Product, membership: Membership):
        """
        Product と Membership の割り当てを解除する
        """
        ProductService._ensure_same_organization(
            product=product,
            membership=membership,
        )

        ProductAssignee.objects.filter(
            product=product,
            membership=membership,
        ).delete()
