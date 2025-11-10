"""Financial institution endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentActiveUser
from app.db.session import get_db
from app.models.financial_institution import FinancialInstitution
from app.schemas.financial_institution import (
    FinancialInstitutionCreate,
    FinancialInstitutionResponse,
    FinancialInstitutionUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[FinancialInstitutionResponse])
async def get_financial_institutions(
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[FinancialInstitution]:
    """
    Get all financial institutions for the current user.

    Args:
        current_user: The authenticated user (from dependency)
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of financial institutions
    """
    result = await db.execute(
        select(FinancialInstitution)
        .where(FinancialInstitution.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("/", response_model=FinancialInstitutionResponse, status_code=status.HTTP_201_CREATED)
async def create_financial_institution(
    institution: FinancialInstitutionCreate,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialInstitution:
    """
    Create a new financial institution.

    Args:
        institution: Financial institution data
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The created financial institution
    """
    db_institution = FinancialInstitution(
        user_id=current_user.id,
        **institution.model_dump(),
    )
    db.add(db_institution)
    await db.commit()
    await db.refresh(db_institution)

    return db_institution


@router.get("/{institution_id}", response_model=FinancialInstitutionResponse)
async def get_financial_institution(
    institution_id: UUID,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialInstitution:
    """
    Get a specific financial institution.

    Args:
        institution_id: The ID of the institution to retrieve
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The requested financial institution

    Raises:
        HTTPException: If institution not found or access denied
    """
    result = await db.execute(
        select(FinancialInstitution).where(FinancialInstitution.id == institution_id)
    )
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial institution not found",
        )

    # Verify ownership
    if institution.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this financial institution",
        )

    return institution


@router.put("/{institution_id}", response_model=FinancialInstitutionResponse)
async def update_financial_institution(
    institution_id: UUID,
    institution_update: FinancialInstitutionUpdate,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialInstitution:
    """
    Update a financial institution.

    Args:
        institution_id: The ID of the institution to update
        institution_update: Updated institution data
        current_user: The authenticated user (from dependency)
        db: Database session

    Returns:
        The updated financial institution

    Raises:
        HTTPException: If institution not found or access denied
    """
    result = await db.execute(
        select(FinancialInstitution).where(FinancialInstitution.id == institution_id)
    )
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial institution not found",
        )

    # Verify ownership
    if institution.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this financial institution",
        )

    # Update fields
    update_data = institution_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(institution, field, value)

    await db.commit()
    await db.refresh(institution)

    return institution


@router.delete("/{institution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_financial_institution(
    institution_id: UUID,
    current_user: CurrentActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete a financial institution.

    Args:
        institution_id: The ID of the institution to delete
        current_user: The authenticated user (from dependency)
        db: Database session

    Raises:
        HTTPException: If institution not found or access denied
    """
    result = await db.execute(
        select(FinancialInstitution).where(FinancialInstitution.id == institution_id)
    )
    institution = result.scalar_one_or_none()

    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial institution not found",
        )

    # Verify ownership
    if institution.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this financial institution",
        )

    await db.delete(institution)
    await db.commit()
