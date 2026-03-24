import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database...');

  // Clear existing data
  await prisma.auditLog.deleteMany();
  await prisma.agentLog.deleteMany();
  await prisma.step.deleteMany();
  await prisma.workflow.deleteMany();
  await prisma.employee.deleteMany();

  // Seed employees
  const employees = await Promise.all([
    prisma.employee.create({
      data: { name: 'Alice Johnson', email: 'alice.johnson@company.com', role: 'Software Engineer', department: 'Engineering', status: 'ACTIVE' },
    }),
    prisma.employee.create({
      data: { name: 'Bob Smith', email: 'bob.smith@company.com', role: 'Product Manager', department: 'Product', status: 'ACTIVE' },
    }),
    prisma.employee.create({
      data: { name: 'Carol Williams', email: 'carol.williams@company.com', role: 'Designer', department: 'Design', status: 'ACTIVE' },
    }),
    prisma.employee.create({
      data: { name: 'David Chen', email: 'david.chen@company.com', role: 'DevOps Engineer', department: 'Engineering', status: 'ACTIVE' },
    }),
    prisma.employee.create({
      data: { name: 'Eva Martinez', email: 'eva.martinez@company.com', role: 'HR Manager', department: 'Human Resources', status: 'ACTIVE' },
    }),
  ]);

  console.log(`Created ${employees.length} employees`);
  console.log('Seeding complete!');
}

main()
  .catch((e) => { console.error('Seeding failed:', e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
