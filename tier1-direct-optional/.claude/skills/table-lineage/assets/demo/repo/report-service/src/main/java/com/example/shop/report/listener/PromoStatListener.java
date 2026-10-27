package com.example.shop.report.listener;

import com.example.shop.common.cdc.CdcEvent;
import com.example.shop.report.mapper.PromoStatMapper;
import javax.annotation.Resource;
import org.springframework.stereotype.Component;

/** Promotion statistics; the listener is switched off since the promotion ended. */
@Component
public class PromoStatListener {

    @Resource
    private PromoStatMapper promoStatMapper;

    // @KafkaListener(topics = "cdc.shop_order", groupId = "report-promo")
    public void onMessage(CdcEvent event) {
        promoStatMapper.increase(event.getDay());
    }
}
