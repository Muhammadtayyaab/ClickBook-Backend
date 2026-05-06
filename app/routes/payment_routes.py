from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.middleware.auth import get_current_user
from app.models import Payment
from app.schemas.payment_schema import PaymentOutputSchema
from app.utils.responses import success_response

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payments_bp.get("/my")
@jwt_required()
def my_payments():
    user = get_current_user()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    pagination = Payment.query.filter_by(user_id=user.id).order_by(Payment.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return success_response(
        PaymentOutputSchema(many=True).dump(pagination.items),
        total=pagination.total,
        page=page,
        per_page=per_page,
        pages=pagination.pages,
    )
