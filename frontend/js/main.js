// サーバ接続時堪忍事項
// ・URLとポート番号が正しいか
// ・変数名がサーバ側と一致しているか


const API_URL = 'http://localhost:3000/api/status'; // 仮のサーバURL

async function updateSeatStatus() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json(); 

        // ストアID（表示はさせないかも？）
        document.getElementById('store_id').innerText = data.store_id;
        
        // 残席数を表示
        document.getElementById('remains-seats').innerText = `${data.remaining_seats}席`;
        
        // 最終更新時刻を表示（Tを半角スペースに置換）-- ★1分間隔更新
        document.getElementById('updated-at').innerText = data.updated_at.replace('T', ' ');
        
        // 詳細更新時刻（カウンター・テーブル更新時刻）を表示 -- ★5分間隔更新
        // （拡張機能のため、仮作成）
        // （実装の場合、API側にも追加してもらう）
        document.getElementById('details-updated-at').innerText = data.details_updated_at.replace('T', ' ');


        // データ鮮度フラグを判定(is_stale: true = 古い / false = 新しい)
        const freshnessElem = document.getElementById('freshness');
        if (data.is_stale) {
            freshnessElem.innerText = "情報が更新されていません";
            freshnessElem.style.color = "orange";
        } else {
            freshnessElem.innerText = "最新";
            freshnessElem.style.color = "green";
        }

        // 席種別データの有無をチェックして分岐
        if (data.counter_vacant !== undefined && data.counter_vacant !== null) {
            // 拡張機能のデータがある場合
            document.getElementById('counter-status').innerText = `${data.counter_vacant} / ${data.counter_total}席空き`;
            document.getElementById('table-status').innerText = `${data.table_vacant} / ${data.table_total}卓空き`;
        } else {
            // 最小構成の場合（フィールドがない、または null のとき）
            document.getElementById('counter-status').innerText = "未対応";
            document.getElementById('table-status').innerText = "未対応";
        }

    } catch (error) {
        console.error('データ取得失敗:', error);
        document.getElementById('seats').innerText = "エラー";
        document.getElementById('freshness').innerText = "通信失敗";
    }
}

// サーバ側で情報が更新されたあと、1分ごとに更新する
window.onload = () => {
    updateSeatStatus();
    setInterval(updateSeatStatus, 60000); 
};