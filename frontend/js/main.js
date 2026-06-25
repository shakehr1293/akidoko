const API_URL = 'http://localhost:3000/api/status'; // 仮のサーバURL

async function updateSeatStatus() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json(); 
        
        // 残席数を表示
        document.getElementById('seats').innerText = data.remainingSeats;
        
        // 最終更新時刻を表示
        document.getElementById('updated-at').innerText = data.lastUpdatedAt;
        
        // データ鮮度フラグを判定して表示を変える（文言は仮）
        const freshnessElem = document.getElementById('freshness');
        if (data.isFresh) {
            freshnessElem.innerText = "最新（リアルタイム）";
            freshnessElem.style.color = "green";
        } else {
            freshnessElem.innerText = "情報が更新されていません";
            freshnessElem.style.color = "orange";
        }

    } catch (error) {
        console.error('データ取得失敗:', error);
        document.getElementById('seats').innerText = "エラー";
        document.getElementById('freshness').innerText = "通信失敗";
    }
}

// ページ読み込み時に実行
window.onload = updateSeatStatus;