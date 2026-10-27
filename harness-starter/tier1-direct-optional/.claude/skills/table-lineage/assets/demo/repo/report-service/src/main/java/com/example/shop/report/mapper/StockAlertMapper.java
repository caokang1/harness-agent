package com.example.shop.report.mapper;

import com.example.shop.common.dto.StockDTO;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface StockAlertMapper {

    int insertAlerts(@Param("ruleId") Long ruleId, @Param("items") List<StockDTO> items);
}
