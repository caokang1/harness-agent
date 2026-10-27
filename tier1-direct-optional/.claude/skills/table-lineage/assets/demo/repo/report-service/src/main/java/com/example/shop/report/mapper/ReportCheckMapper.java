package com.example.shop.report.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface ReportCheckMapper {

    @Select("select count(*) from ${table}")
    long countRows(@Param("table") String table);

    @Insert("insert into report_check_log (report, row_count) values (#{report}, #{rows})")
    int log(@Param("report") String report, @Param("rows") long rows);
}
