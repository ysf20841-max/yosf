// ==========================================
// 1. التحكم بالقائمة الجانبية للهواتف (Mobile Menu)
// ==========================================
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    if (menu) {
        menu.classList.toggle('hidden');
    }
}

// إغلاق القائمة عند الضغط خارج النافذة
document.addEventListener('click', function (e) {
    const menu = document.getElementById('mobile-menu');
    const menuBtn = e.target.closest('button[onclick="toggleMobileMenu()"]');
    
    if (menu && !menu.classList.contains('hidden') && !menu.contains(e.target) && !menuBtn) {
        menu.classList.add('hidden');
    }
});

// ==========================================
// 2. التحكم بالوضع الليلي والنهاري (Dark / Light Mode)
// ==========================================
function toggleDarkMode() {
    const html = document.documentElement;
    const isDark = html.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// تطبيق الثيم المحفوظ عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function () {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.documentElement.classList.remove('dark');
    } else {
        document.documentElement.classList.add('dark');
    }
    updatePricesDisplay();
});

// ==========================================
// 3. تحويل العملة وتحديث الأسعار (USD / SYP)
// ==========================================
let currentCurrency = 'USD';

function toggleCurrency() {
    currentCurrency = currentCurrency === 'USD' ? 'SYP' : 'USD';
    const currencyBtn = document.getElementById('currency-btn');
    if (currencyBtn) {
        currencyBtn.innerText = currentCurrency === 'USD' ? 'USD' : 'SYP';
    }
    updatePricesDisplay();
    calculateModalTotal(); // إعادة حساب إجمالي النافذة المنبثقة إن كانت مفتوحة
}

function updatePricesDisplay() {
    document.querySelectorAll('.price-tag').forEach(el => {
        const usd = parseFloat(el.getAttribute('data-usd')) || 0;
        const syp = parseFloat(el.getAttribute('data-syp')) || (usd * 150);
        if (currentCurrency === 'SYP') {
            el.innerText = syp.toLocaleString('ar-EG') + ' ل.س';
        } else {
            el.innerText = '$' + usd.toFixed(2);
        }
    });
}

// ==========================================
// 4. التحكم بالنافذة المنبثقة للطلب (Order Modal)
// ==========================================
let modalUsd = 0;
let modalSyp = 0;

function openOrderModal(id, name, priceUsd, priceSyp, minQ, maxQ) {
    const modal = document.getElementById('order-modal');
    if (!modal) return;

    document.getElementById('modal-service-id').value = id;
    document.getElementById('modal-service-title').innerText = 'طلب: ' + name;
    
    const limitsEl = document.getElementById('modal-limits-text');
    if (limitsEl) {
        limitsEl.innerText = `الحد الأدنى: ${minQ} - الحد الأقصى: ${maxQ}`;
    }

    const qInput = document.getElementById('modal-quantity');
    if (qInput) {
        qInput.value = minQ || 100;
        qInput.min = minQ || 1;
        qInput.max = maxQ || 100000;
    }

    modalUsd = priceUsd;
    modalSyp = priceSyp;

    calculateModalTotal();
    modal.classList.remove('hidden');
}

function closeOrderModal() {
    const modal = document.getElementById('order-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function calculateModalTotal() {
    const qInput = document.getElementById('modal-quantity');
    const totalEl = document.getElementById('modal-total-price');
    if (!qInput || !totalEl) return;

    const qty = parseInt(qInput.value) || 0;

    if (currentCurrency === 'SYP') {
        const total = (modalSyp / 1000) * qty;
        totalEl.innerText = total.toLocaleString('ar-EG') + ' ل.س';
    } else {
        const total = (modalUsd / 1000) * qty;
        totalEl.innerText = '$' + total.toFixed(2);
    }
}