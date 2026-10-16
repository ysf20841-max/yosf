// تعريف المتغيرات العامة
let selectedServicePriceUsd = 0;
let selectedServicePriceSyp = 0;

// دالة تحميل وتوليد الأقسام في الصفحة الرئيسية
function loadCategories() {
    const catContainer = document.getElementById('categories-container');
    if (!catContainer) return;
    catContainer.innerHTML = '';

    const allServices = window.allServices || [];
    const categoriesMap = {};
    
    allServices.forEach(s => {
        if (s && s.category && !categoriesMap[s.category]) {
            categoriesMap[s.category] = { 
                name: s.category, 
                image: s.image_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400' 
            };
        }
    });

    const uniqueCats = Object.values(categoriesMap);
    if (uniqueCats.length === 0) {
        catContainer.innerHTML = '<p class="col-span-full text-center text-gray-500 text-xs py-4 bg-[#131c2e] rounded-2xl border border-gray-800">لا توجد خدمات مضافة حالياً. اذهب لوحة الأدمن لإضافة أول خدمة!</p>';
        return;
    }

    uniqueCats.forEach(cat => {
        const card = document.createElement('div');
        card.className = 'cursor-pointer bg-cardBg border border-gray-800 rounded-2xl p-3 active:scale-95 transition shadow hover:border-cyan-500';
        card.onclick = () => selectCategory(cat.name);
        card.innerHTML = `
            <div class="h-24 rounded-xl overflow-hidden mb-2 bg-gray-900">
                <img src="${cat.image}" class="w-full h-full object-cover">
            </div>
            <h3 class="text-xs font-bold text-cyan-400 truncate">${cat.name}</h3>
            <p class="text-gray-400 text-[10px]">استعراض الخدمات</p>
        `;
        catContainer.appendChild(card);
    });
}

// دالة اختيار القسم وإظهار الخدمات التابعة له حصراً
function selectCategory(catName) {
    const container = document.getElementById('services-cards-container');
    const title = document.getElementById('category-title');
    const gridSection = document.getElementById('services-grid-section');
    
    if (!container || !title || !gridSection) return;

    // إظهار قسم الخدمات عند النقر على القسم
    gridSection.classList.remove('hidden');

    container.innerHTML = '';
    title.innerText = 'قسم: ' + catName;

    const allServices = window.allServices || [];
    const filtered = allServices.filter(s => s && s.category === catName);

    if (filtered.length === 0) {
        container.innerHTML = '<p class="text-center text-gray-500 text-xs py-4 col-span-full">لا توجد خدمات في هذا القسم.</p>';
        return;
    }

    filtered.forEach(s => {
        const card = document.createElement('div');
        card.className = 'bg-cardBg border border-gray-800 rounded-2xl p-3 flex flex-col justify-between shadow';
        
        let badge = s.is_available 
            ? '<span class="bg-emerald-500/20 text-emerald-400 text-[9px] px-2 py-0.5 rounded-full font-bold">متوفرة</span>'
            : '<span class="bg-rose-600 text-white text-[9px] px-2 py-0.5 rounded-full font-bold">غير متوفرة</span>';

        let btn = s.is_available
            ? `<button onclick="openOrderForm(${s.id})" class="w-full mt-3 bg-cyan-500 text-gray-950 font-bold py-2 rounded-xl text-xs active:scale-95">اطلب الآن</button>`
            : `<button disabled class="w-full mt-3 bg-gray-800 text-gray-500 py-2 rounded-xl text-xs">غير متوفرة</button>`;

        card.innerHTML = `
            <div>
                <div class="flex justify-between items-start mb-2">
                    <h4 class="text-xs font-bold text-white">${s.name}</h4>
                    ${badge}
                </div>
                <p class="text-cyan-400 font-bold text-xs price-tag" data-usd="${s.price_usd}" data-syp="${s.price_syp || 0}">
                    $${s.price_usd.toFixed(2)}
                </p>
            </div>
            ${btn}
        `;
        container.appendChild(card);
    });

    if (typeof updatePricesDisplay === 'function') {
        updatePricesDisplay();
    }
    gridSection.scrollIntoView({ behavior: 'smooth' });
}

// فتح نموذج الطلب السريع عند اختيار خدمة
function openOrderForm(serviceId) {
    const service = (window.allServices || []).find(s => s && s.id === serviceId);
    if (!service) return;

    document.getElementById('service_id_input').value = service.id;
    document.getElementById('selected-service-title').innerText = 'طلب: ' + service.name;
    selectedServicePriceUsd = service.price_usd;
    selectedServicePriceSyp = service.price_syp || 0;

    calculateTotal();
    const orderSec = document.getElementById('order-section');
    orderSec.classList.remove('hidden');
    orderSec.scrollIntoView({ behavior: 'smooth' });
}

// حساب السعر الإجمالي تلقائياً بناءً على الكمية والعملة
function calculateTotal() {
    const qty = parseInt(document.getElementById('quantity_input').value) || 0;
    const priceEl = document.getElementById('total-price');
    if (!priceEl) return;

    if (typeof currentCurrency !== 'undefined' && currentCurrency === 'SYP' && selectedServicePriceSyp > 0) {
        const total = (selectedServicePriceSyp / 1000) * qty;
        priceEl.innerText = total.toLocaleString() + ' ل.س';
    } else {
        const total = (selectedServicePriceUsd / 1000) * qty;
        priceEl.innerText = '$' + total.toFixed(2);
    }
}

// تحديث عرض الأسعار للعملتين (دولار / ليرة سورية)
function updatePricesDisplay() {
    const btn = document.getElementById('currency-btn');
    if(btn) btn.innerText = (typeof currentCurrency !== 'undefined' && currentCurrency === 'SYP') ? 'SYP (ل.س)' : 'USD ($)';
    
    document.querySelectorAll('.price-tag').forEach(el => {
        const usd = parseFloat(el.getAttribute('data-usd')) || 0;
        const syp = parseFloat(el.getAttribute('data-syp')) || 0;
        if(typeof currentCurrency !== 'undefined' && currentCurrency === 'SYP' && syp > 0) {
            el.innerText = syp.toLocaleString() + ' ل.س';
        } else {
            el.innerText = '$' + usd.toFixed(2);
        }
    });
}

// تشغيل الأقسام عند تحميل الصفحة
window.addEventListener('DOMContentLoaded', () => {
    loadCategories();
});