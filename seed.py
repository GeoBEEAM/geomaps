# seed.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import engine
from core.security import generate_password_hash
from models.user import User
from models.profile import Profile

async def seed_data():
    async with AsyncSession(engine) as session:
        async with session.begin():
            # Perfis
            admin_profile = Profile(name="Admin")
            apicultor_profile = Profile(name="Apicultor")
            meliponicultor_profile = Profile(name="Meliponicultor")
            session.add_all([admin_profile, apicultor_profile, meliponicultor_profile])

            # Usuários
            password = generate_password_hash("12345678")
            admin_user = User(fullName="Admin GeoBee", cpf="000000001", phone="999999999", email="admin@geobee.app", password=password)
            apic_user = User(fullName="Demonstração Apiário", cpf="000000002", phone="888888888", email="apic@geobee.app", password=password)
            meli_user = User(fullName="Demonstração Meliponário", cpf="000000003", phone="777777777", email="meli@geobee.app", password=password)
            # Relaciona perfis aos usuários
            admin_user.profiles.append(admin_profile)
            apic_user.profiles.append(apicultor_profile)
            meli_user.profiles.append(meliponicultor_profile)
            session.add_all([admin_user, apic_user, meli_user])
        await session.commit()
        print("Seed data inserted successfully!")

if __name__ == '__main__':
    asyncio.run(seed_data())