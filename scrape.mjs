import 'dotenv/config';
import { createScraper, CompanyTypes } from 'israeli-bank-scrapers';

const credentials = {
  username: process.env.LEUMI_USERNAME,
  password: process.env.LEUMI_PASSWORD,
};

if (!credentials.username || !credentials.password) {
  console.error('❌ חסרים פרטי התחברות. הגדר LEUMI_USERNAME ו-LEUMI_PASSWORD');
  process.exit(1);
}

console.log('🔄 מתחבר ללאומי...');

const scraper = createScraper({
  companyId: CompanyTypes.leumi,
  startDate: new Date(new Date().getFullYear(), new Date().getMonth() - 2, 1), // 3 חודשים אחורה
  showBrowser: true,
});

try {
  const result = await scraper.scrape(credentials);

  if (!result.success) {
    console.error('❌ שגיאה בשליפה:', result.errorType, result.errorMessage);
    process.exit(1);
  }

  for (const account of result.accounts) {
    console.log(`\n📋 חשבון: ${account.accountNumber}`);
    console.log(`   סה"כ עסקאות: ${account.txns.length}`);

    const byMonth = {};
    for (const txn of account.txns) {
      const month = txn.date.substring(0, 7); // YYYY-MM
      if (!byMonth[month]) byMonth[month] = [];
      byMonth[month].push(txn);
    }

    for (const [month, txns] of Object.entries(byMonth).sort()) {
      const total = txns.reduce((sum, t) => sum + t.chargedAmount, 0);
      console.log(`\n   📅 ${month}`);
      console.log(`   סה"כ הוצאות: ₪${Math.abs(total).toLocaleString('he-IL')}`);
      console.log('   ─────────────────────────────────────');
      for (const t of txns.slice(0, 10)) {
        console.log(`   ${t.date.substring(0, 10)}  ₪${Math.abs(t.chargedAmount).toString().padStart(8)}  ${t.description}`);
      }
      if (txns.length > 10) console.log(`   ... ועוד ${txns.length - 10} עסקאות`);
    }
  }

  // שמירת הנתונים לקובץ JSON
  const fs = await import('fs');
  const output = {
    scrapedAt: new Date().toISOString(),
    accounts: result.accounts,
  };
  fs.writeFileSync('transactions.json', JSON.stringify(output, null, 2));
  console.log('\n✅ הנתונים נשמרו ב-transactions.json');

} catch (err) {
  console.error('❌ שגיאה:', err.message);
  process.exit(1);
}
