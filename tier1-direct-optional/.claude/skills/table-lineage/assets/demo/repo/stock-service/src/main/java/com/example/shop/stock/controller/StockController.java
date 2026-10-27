package com.example.shop.stock.controller;

import com.example.shop.common.api.StockApi;
import com.example.shop.common.dto.StockDTO;
import com.example.shop.stock.mapper.StockMapper;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class StockController implements StockApi {

    @Resource
    private StockMapper stockMapper;

    @Override
    public List<StockDTO> listLowStock(Integer threshold) {
        return stockMapper.selectLow(threshold);
    }
}
