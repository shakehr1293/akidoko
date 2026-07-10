const API_URL = 'http://10.77.99.164:3000/api/status';

// カウンター・テーブル共通の更新処理
function updateSeatCard(id, vacant, total) {
    const container = document.getElementById(id);
    const vacantEl = container.querySelector('.vacant-num');
    const totalEl = container.querySelector('.total-num');

    vacantEl.innerText = (vacant === 0) ? '満席' : vacant;
    totalEl.innerText = total;

    // 空き状況に応じて色分け
    const ratio = total === 0 ? 0 : vacant / total;
    vacantEl.style.color =
        vacant === 0 ? '#c62828' :
        ratio < 0.3 ? '#f9a825' :
        '#2e7d32';
}

async function updateSeatStatus() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json();

        // 残席数を表示
        document.getElementById('remaining-seats').innerText = `${data.remaining_seats}席`;

        // 最終更新時刻を表示
        document.getElementById('updated-at').innerText = data.updated_at.replace('T', ' ');

        // データ鮮度フラグを判定
        const freshnessElem = document.getElementById('freshness');
        if (data.is_stale) {
            freshnessElem.innerText = "情報が更新されていません";
            freshnessElem.style.color = "orange";
        } else {
            freshnessElem.innerText = "最新";
            freshnessElem.style.color = "green";
        }

        // カウンター・テーブルの残席を更新
        updateSeatCard('counter-status', data.counter_vacant, data.counter_total);
        updateSeatCard('table-status', data.table_vacant, data.table_total);

        // 各カードの更新時刻
        document.getElementById('counter-updated-at').innerText = data.updated_at.replace('T', ' ');
        document.getElementById('table-updated-at').innerText = data.updated_at.replace('T', ' ');

    } catch (error) {
        console.error('データ取得失敗:', error);
        document.getElementById('remaining-seats').innerText = "エラー";
        document.getElementById('freshness').innerText = "通信失敗";
    }
}

window.onload = () => {
    updateSeatStatus();
    setInterval(updateSeatStatus, 60000);
};