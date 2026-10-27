package com.example.shop.stock.controller;

import com.example.shop.stock.mapper.StockMapper;
import javax.annotation.Resource;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class StockAdjustController {

    @Resource
    private StockMapper stockMapper;

    @Transactional
    @PostMapping("/stock/adjust")
    public void adjust(@RequestParam("stockId") Long stockId, @RequestParam("delta") Integer delta) {
        stockMapper.adjust(stockId, delta);
        stockMapper.log(stockId, delta);
    }
}
